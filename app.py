import io
import time
from datetime import datetime
from http.cookiejar import MozillaCookieJar

import requests
from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- 상수 정의 ---
COOKIE_PATH = "./cookies.txt"
IMG_SIZE = (450, 450)
CANVAS_SIZE = (800, 450)
FONT_PATH = './src/PretendardJPVariable.ttf'
FONT_SIZE = 30
NICKNAME_FONT_SIZE = 22

# --- 웹 드라이버 옵션 설정 ---
options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--enable-unsafe-swiftshader')
options.add_argument(
    'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/98.0.4758.102 Safari/537.36'
)

# --- 메인 로직 ---
cookie_jar = MozillaCookieJar(COOKIE_PATH)
cookie_jar.load(ignore_discard=True, ignore_expires=True)

tweet_link = input('Input link: ')
tweet_author = tweet_link.split('/')[3]

print('Getting Tweet...')
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()), options=options
)

driver.get(tweet_link)
for cookie in cookie_jar:
    cookie_dict = {
        'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain,
        'path': cookie.path, 'secure': cookie.secure, 'expiry': cookie.expires
    }
    driver.add_cookie(cookie_dict)
driver.refresh()
driver.implicitly_wait(15)

# 트윗 내용 XPATH
content_xpath = '/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/section/div/div/div[1]/div/div/article/div/div/div[3]/div[1]/div/div/span'
content_xpath_alt = '/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/section/div/div/div[2]/div/div/article/div/div/div[3]/div[1]/div/div[2]/span'

# 닉네임 XPATH
nickname_xpath = '/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/section/div/div/div[1]/div/div/article/div/div/div[2]/div[2]/div/div/div[1]/div/div/div[1]/div/a/div/div[1]/span/span'
nickname_xpath_alt = '/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/section/div/div/div[2]/div/div/article/div/div/div[2]/div[2]/div/div/div[1]/div/div/div[1]/div/a/div/div[1]/span/span'

try:
    tweet_content = driver.find_element(By.XPATH, content_xpath).text
    tweet_nickname = driver.find_element(By.XPATH, nickname_xpath).text
except Exception:
    tweet_content = driver.find_element(By.XPATH, content_xpath_alt).text
    tweet_nickname = driver.find_element(By.XPATH, nickname_xpath_alt).text

# 이미지 주소 가져오기
time.sleep(3)
photo_link = f"https://x.com/{tweet_author}/photo"
driver.get(photo_link)
driver.implicitly_wait(15)
img_xpath = '/html/body/div/div/div/div[1]/div[2]/div/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div/div/img'
img_src = driver.find_element(By.XPATH, img_xpath).get_attribute('src')
driver.quit()

# 이미지 다운로드 및 처리
try:
    response = requests.get(img_src)
    response.raise_for_status()
    image_bytes = io.BytesIO(response.content)
    source_image = Image.open(image_bytes)
except requests.exceptions.RequestException as e:
    print(f"Download image failed: {e}")
    source_image = None

if source_image:
    source_image = source_image.convert("RGBA").resize(IMG_SIZE)

    canvas = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 255))
    mask = Image.new('L', IMG_SIZE, 0)
    draw_mask = ImageDraw.Draw(mask)

    fade_start_x = IMG_SIZE[0] // 2
    for x in range(IMG_SIZE[0]):
        alpha = 255 if x < fade_start_x else int(255 * (1 - (x - fade_start_x) / (IMG_SIZE[0] - fade_start_x)))
        draw_mask.line([(x, 0), (x, IMG_SIZE[1])], fill=alpha)
    canvas.paste(source_image, (0, 0), mask)

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        # 닉네임용 폰트 객체 생성
        nickname_font = ImageFont.truetype(FONT_PATH, NICKNAME_FONT_SIZE)
    except (IOError, FileNotFoundError):
        print("지정한 폰트 파일을 찾을 수 없습니다. 기본 폰트를 사용합니다.")
        font = ImageFont.load_default()
        nickname_font = ImageFont.load_default()

    text_x_start = 475
    max_text_width = CANVAS_SIZE[0] - text_x_start - 25
    lines = []
    current_line = ""

    for char in tweet_content:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]
        if line_width <= max_text_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)
    wrapped_text = "\n".join(lines)

    text_bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_height = text_bbox[3] - text_bbox[1]
    text_y_start = (CANVAS_SIZE[1] - text_height) / 2

    # 메인 트윗 내용 그리기
    draw.multiline_text(
        (text_x_start, text_y_start), wrapped_text, font=font,
        fill=(255, 255, 255, 255), align='center'
    )
    
    nickname_bbox = draw.textbbox((0, 0), tweet_nickname, font=nickname_font)
    nickname_width = nickname_bbox[2] - nickname_bbox[0]

    text_area_width = CANVAS_SIZE[0] - text_x_start

    nickname_x_start = text_x_start + (text_area_width - nickname_width) / 2 - 20
    nickname_y_start = text_y_start + text_height + 15

    draw.text(
        (nickname_x_start, nickname_y_start),
        tweet_nickname,
        font=nickname_font,
        fill=(150, 150, 150, 255), # 회색
        align='center'
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{tweet_author}_{timestamp}.png"
    
    canvas.save(output_filename)
    print(f"이미지가 성공적으로 '{output_filename}' 경로에 저장되었습니다.")