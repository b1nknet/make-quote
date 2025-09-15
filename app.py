# Standard library imports
import io
from datetime import datetime
from http.cookiejar import MozillaCookieJar

# Third-party imports
import requests
from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONSTANTS ---
COOKIE_PATH = "./cookies.txt"
FONT_PATH = './src/PretendardJPVariable.ttf'
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/98.0.4758.102 Safari/537.36'
)

# Image and Font settings
IMG_SIZE = (450, 450)
CANVAS_SIZE = (800, 450)
FONT_SIZE = 30
NICKNAME_FONT_SIZE = 22

# XPaths for scraping
CONTENT_XPATHS = [
    '/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/section/div/div/div[1]/div/div/article/div/div/div[3]/div[1]/div/div/span',
    '/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/section/div/div/div[2]/div/div/article/div/div/div[3]/div[1]/div/div[2]/span'
]
NICKNAME_XPATHS = [
    '/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/section/div/div/div[1]/div/div/article/div/div/div[2]/div[2]/div/div/div[1]/div/div/div[1]/div/a/div/div[1]/span/span',
    '/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/section/div/div/div[2]/div/div/article/div/div/div[2]/div[2]/div/div/div[1]/div/div/div[1]/div/a/div/div[1]/span/span'
]
IMAGE_XPATH = '/html/body/div/div/div/div[1]/div[2]/div/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div/div/img'


def setup_driver():
    """Sets up and initializes the Selenium WebDriver."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--enable-unsafe-swiftshader')
    options.add_argument(f'user-agent={USER_AGENT}')

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    return driver


def load_cookies(driver, cookie_path):
    """Loads cookies from a specified file path into the WebDriver."""
    cookie_jar = MozillaCookieJar(cookie_path)
    cookie_jar.load(ignore_discard=True, ignore_expires=True)
    for cookie in cookie_jar:
        cookie_dict = {
            'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain,
            'path': cookie.path, 'secure': cookie.secure,
            'expiry': cookie.expires
        }
        driver.add_cookie(cookie_dict)
    return driver


def find_element_by_xpaths(driver, xpaths):
    """Finds an element using one of several possible XPaths and returns its text."""
    for xpath in xpaths:
        try:
            element = driver.find_element(By.XPATH, xpath)
            return element.text
        except NoSuchElementException:
            continue
    raise NoSuchElementException(f"Elements not found with provided XPaths: {xpaths}")


def scrape_tweet_data(driver, tweet_link):
    """Scrapes the nickname, content, and profile image URL from a tweet link."""
    print('Getting Tweet content and nickname...')
    driver.get(tweet_link)
    driver.refresh()
    driver.implicitly_wait(15)

    tweet_content = find_element_by_xpaths(driver, CONTENT_XPATHS)
    tweet_nickname = find_element_by_xpaths(driver, NICKNAME_XPATHS)

    print('Getting profile image URL...')
    tweet_author = tweet_link.split('/')[3]
    photo_link = f"https://x.com/{tweet_author}/photo"
    driver.get(photo_link)
    driver.implicitly_wait(15)

    img_src = driver.find_element(By.XPATH, IMAGE_XPATH).get_attribute('src')

    return tweet_content, tweet_nickname, img_src


def download_image(img_src):
    """Downloads an image from a URL and returns a Pillow Image object."""
    try:
        response = requests.get(img_src)
        response.raise_for_status()
        image_bytes = io.BytesIO(response.content)
        return Image.open(image_bytes)
    except requests.exceptions.RequestException as e:
        print(f"Failed to download image: {e}")
        return None


def wrap_text(draw, text, font, max_width):
    """Wraps text character by character to fit within a given maximum width."""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]
        if line_width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)
    return "\n".join(lines)


def create_tweet_image(source_image, tweet_content, tweet_nickname):
    """Combines the profile image and text to create the final image."""
    # 1. Prepare source image and canvas
    source_image = source_image.convert("RGBA").resize(IMG_SIZE)
    canvas = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 255))

    # 2. Apply a fade-out mask to the image
    mask = Image.new('L', IMG_SIZE, 0)
    draw_mask = ImageDraw.Draw(mask)
    fade_start_x = IMG_SIZE[0] // 2
    for x in range(IMG_SIZE[0]):
        alpha = 255 if x < fade_start_x else int(
            255 * (1 - (x - fade_start_x) / (IMG_SIZE[0] - fade_start_x))
        )
        draw_mask.line([(x, 0), (x, IMG_SIZE[1])], fill=alpha)
    canvas.paste(source_image, (0, 0), mask)

    # 3. Load fonts
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        nickname_font = ImageFont.truetype(FONT_PATH, NICKNAME_FONT_SIZE)
    except (IOError, FileNotFoundError):
        print("Font file not found. Using default font.")
        font = ImageFont.load_default()
        nickname_font = ImageFont.load_default()

    # 4. Wrap text and calculate its position
    text_x_start = 475
    max_text_width = CANVAS_SIZE[0] - text_x_start - 25
    wrapped_text = wrap_text(draw, tweet_content, font, max_text_width)

    text_bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    text_area_width = CANVAS_SIZE[0] - text_x_start - 25
    centered_x = text_x_start + (text_area_width - text_width) / 2
    centered_y = (CANVAS_SIZE[1] - text_height) / 2

    # 5. Draw the tweet content
    draw.multiline_text(
        (centered_x, centered_y), wrapped_text, font=font,
        fill=(255, 255, 255, 255), align='center'
    )

    # 6. Calculate nickname position and draw it
    nickname_bbox = draw.textbbox((0, 0), tweet_nickname, font=nickname_font)
    nickname_width = nickname_bbox[2] - nickname_bbox[0]
    nickname_x = centered_x + (text_width - nickname_width) / 2
    nickname_y = centered_y + text_height + 15

    draw.text(
        (nickname_x, nickname_y), tweet_nickname,
        font=nickname_font, fill=(150, 150, 150, 255), align='center'
    )

    return canvas


def main():
    """The main execution function of the script."""
    tweet_link = input('Input link: ')

    driver = setup_driver()
    try:
        # Visit the site first to set the domain for the cookies
        driver.get("https://x.com")
        load_cookies(driver, COOKIE_PATH)

        content, nickname, img_src = scrape_tweet_data(driver, tweet_link)

        print('Downloading image...')
        source_image = download_image(img_src)

        if source_image:
            print('Creating final image...')
            final_image = create_tweet_image(source_image, content, nickname)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            tweet_author = tweet_link.split('/')[3]
            output_filename = f"{tweet_author}_{timestamp}.png"

            final_image.save(output_filename)
            print(f"이미지가 성공적으로 '{output_filename}' 경로에 저장되었습니다.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print('Closing WebDriver.')
        driver.quit()


if __name__ == "__main__":
    main()