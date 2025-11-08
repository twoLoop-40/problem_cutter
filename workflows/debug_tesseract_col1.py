"""
Tesseract로 col_1에서 "3."을 찾을 수 있는지 확인
"""

from pathlib import Path
import pytesseract
from PIL import Image
import cv2
import numpy as np

# col_1 이미지 로드
img_path = Path("output/생명과학_page1_test/page_1/col_1.png")
img = cv2.imread(str(img_path))
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

print("=" * 80)
print("Tesseract 전체 OCR 결과 (필터링 없음)")
print("=" * 80)

# Tesseract 전체 결과
data = pytesseract.image_to_data(img_rgb, output_type=pytesseract.Output.DICT, lang='kor+eng')

# 모든 텍스트 출력
for i in range(len(data['text'])):
    text = data['text'][i].strip()
    conf = int(data['conf'][i])
    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]

    if text and conf > 0:  # 빈 텍스트가 아니고 confidence > 0
        # "3" 또는 "3." 포함하는 것만
        if '3' in text:
            print(f"  텍스트: '{text}' | conf={conf} | x={x}, y={y}, w={w}, h={h}")

print("\n" + "=" * 80)
print("'3.'을 정확히 포함하는 결과만")
print("=" * 80)

for i in range(len(data['text'])):
    text = data['text'][i].strip()
    conf = int(data['conf'][i])
    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]

    if '3.' in text:
        print(f"  텍스트: '{text}' | conf={conf} | x={x}, y={y}, w={w}, h={h}")

print("\n" + "=" * 80)
print("파라미터 변경 테스트: PSM=6 (전체 페이지)")
print("=" * 80)

data2 = pytesseract.image_to_data(img_rgb, output_type=pytesseract.Output.DICT, lang='kor+eng', config='--psm 6')

for i in range(len(data2['text'])):
    text = data2['text'][i].strip()
    conf = int(data2['conf'][i])
    x, y, w, h = data2['left'][i], data2['top'][i], data2['width'][i], data2['height'][i]

    if '3' in text:
        print(f"  텍스트: '{text}' | conf={conf} | x={x}, y={y}, w={w}, h={h}")
