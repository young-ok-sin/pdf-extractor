
import fitz
import re
import os
import csv
import logging
import warnings

# fitz 워닝 필터 설정
warnings.filterwarnings('ignore', category=RuntimeWarning)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# MuPDF 에러 메시지 출력 제어
fitz.TOOLS.mupdf_display_errors(False)

class PDFProcessingError(Exception):
    """PDF 처리 중 발생하는 커스텀 예외"""
    pass

# book 코드와 다른 메서드
def remove_unnecessary_elements(text: str) -> str:
    """
    알파벳(대/소문자)과 기본 문장 부호((),.'";:-)만 남기고 나머지 문자를 제거하는 함수
    연속된 마침표와 하이픈을 제거합니다(공백 포함/미포함 모두 처리)
    연속적인 소괄호와 그 사이의 쉼표를 제거합니다
    반복되는 숫자 패턴을 제거합니다
    
    Args:
        text (str): 정제할 텍스트
    
    Returns:
        str: 정제된 텍스트
    """
    # 1. 허용할 문자 패턴 정의
    allowed_pattern = r'[^a-zA-Z0-9&(),.\'";\s:-]'
    
    # 2. 허용되지 않는 모든 문자 제거
    cleaned_text = re.sub(allowed_pattern, '', text)
    
    cleanup_patterns = [
        # 1. 괄호 처리
        (r'\(\s*\)', ''),                           # 빈 괄호 제거
        (r'\(\s*,\s*\)', ''),                       # 쉼표만 있는 괄호 제거
        (r'\((?:Fig\.|Figre\.|[.,]+)\)', ''),       # 특정 문자열이 있는 괄호 삭제
        (r'\([.,\s]+\)', ''),                       # 구두점만 있는 괄호 삭제
        (r'\(\(+([^()]*)\)+\)', r'(\1)'),          # 중첩 괄호 처리
        (r'\(\s*(.+?)\s*\)', r'(\1)'),             # 일반적인 괄호 처리
        
        (r'\(\s*[,.]\s*(.*?)\)', r'(\1)'),            # 괄호 안 시작 부분의 쉼표/마침표 제거
        (r'\(\s+[,.]\s*(.*?)\)', r'(\1)'),            # 괄호 안 시작 부분의 공백+쉼표/마침표 제거
        (r'\(\s*(.*?)\s*[,.]\s*\)', r'(\1)'),         # 괄호 안 끝 부분의 쉼표/마침표 제거
        (r'\(\s*(.*?)\s+[,.]\)', r'(\1)'),             # 괄호 안 끝 부분의 공백+쉼표/마침표 제거
        
        # 2. 수식 변수 제거
        (r'\b[a-zA-Z](?:[\s,.]+[a-zA-Z])+\b', ''), # 연속된 변수 제거
        
        # 3. 숫자와 특수문자 처리
        (r'\b\d+(?:\s*[,.-]\s*\d+)*\b', ''),       # 숫자 패턴 제거
        (r'([a-z])-\s+([a-z])', r'\1\2'),          # 하이픈으로 연결된 문자 처리
        (r'-(?:\s*-)+', '-'),                       # 연속된 하이픈 처리
        (r'(\w)\s+\1(?:\s+\1){2,}', ''),           # 반복되는 문자 제거
        
        # 4. 구두점 정리
        (r'\.{2,}', '.'),                           # 연속된 마침표
        (r',{2,}', ','),                            # 연속된 쉼표
        (r'[.,]{2,}', ','),                         # 2개 이상 연속된 구두점을 쉼표로
        (r'\s*[.,]+\s*(?=[.,])', ''),              # 다음 구두점 앞의 구두점 제거
        (r'[.,]+(?=\s*$)', '.'),                    # 문장 끝의 구두점은 마침표로
        (r'\s+\.', '.'),                            # 마침표 앞 공백 제거
        (r'"{2,}', '"'),                           # 연속된 큰따옴표
        (r"'{2,}", "'"),                           # 연속된 작은따옴표
        (r'["\']{2,}', '"'),
        
        # 5. 공백 정리 
        (r'[ \s]{2,}', ' '),                        # 연속된 공백 정리
        (r'\s+,', ','),                             # 쉼표 앞 공백 제거
        (r'\s*([,.])\s*(?=[,.!?])', r'\1'),        # 구두점 사이 공백
        (r',\s+', ', '),                            # 쉼표 뒤 공백 표준화
        (r'\s+', ' ')                               # 남은 연속 공백 정리
    ]

    prev_text = None
    while prev_text != cleaned_text:
        prev_text = cleaned_text
        for pattern, replacement in cleanup_patterns:
            cleaned_text = re.sub(pattern, replacement, cleaned_text)
    return cleaned_text.strip()

def clean_text(text: str) -> str:
    """텍스트에서 불필요한 공백, 탭, 줄바꿈 등을 제거하는 함수"""
    try:
        text = re.sub(r'[\t\r\f\v]+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = remove_unnecessary_elements(text)
        
        return text.strip()
    except Exception as e:
        logging.warning(f"텍스트 정제 중 오류 발생: {str(e)}")
        return ""

def split_into_sentences(text: str) -> list:
    """마침표와 줄바꿈을 기준으로 문장 분리하고 콜론 제거"""
    try:
        # 문장 분리
        sentences = re.split(r'(?<=\.)\s|\n|(?<=;)\s|(?<=:)\s', text)
        
        # 각 문장에서 콜론 제거 후 정리
        cleaned_sentences = []
        for sentence in sentences:
            if sentence and sentence.strip():
                # 콜론 제거
                cleaned = re.sub(r'[;:]', '', sentence.strip())
                cleaned_sentences.append(cleaned)
        return cleaned_sentences
    except Exception as e:
        logging.warning(f"문장 분리 중 오류 발생: {str(e)}")
        return []

def write_excluded_doc(writer: csv.DictWriter, doc_id: str, reason: str, error: str = "None"):
    """제외된 문서 정보를 CSV에 기록하는 함수"""
    try:
        writer.writerow({
            'doc_id': doc_id,
            'reason': reason,
            'error': error
        })
    except Exception as e:
        logging.error(f"제외 문서 기록 중 오류 발생 - doc_id: {doc_id}, error: {str(e)}")

def safe_get_text(page: fitz.Page) -> str:
    """안전하게 페이지 텍스트를 추출하는 함수"""
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            return page.get_text()
        except (RuntimeError, ValueError) as e:
            if "cmsOpenProfileFromMem failed" in str(e) or "invalid ICC colorspace" in str(e):
                if attempt < MAX_RETRIES - 1:
                    continue
            logging.warning(f"텍스트 추출 중 오류 발생 (시도 {attempt + 1}/{MAX_RETRIES}): {str(e)}")
            return ""
        except Exception as e:
            logging.warning(f"알 수 없는 텍스트 추출 오류: {str(e)}")
            return ""
    return ""

# book 코드와 다른 메서드
def check_document_validity(text: str) -> tuple[bool, str]:
    """문서 전체의 유효성을 검사하는 함수
    
    Returns:
        tuple[bool, str]: (유효성 여부, 제외 이유)
    """
    # 빈 문서 체크
    if not text.strip():
        return False, "빈 문서"
        
    # 기본 통계 계산
    total_chars = len(text)
    if total_chars == 0:
        return False, "내용이 없는 문서"
    
    # 특수문자 관련 통계
    special_chars = sum(1 for c in text if c in '"\'(),&-.')
    quotes_count = text.count('"')
    consecutive_quotes = len(re.findall(r'"{2,}', text))
    
    # 한글/영문 문자 수
    korean_chars = len(re.findall(r'[가-힣]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    meaningful_chars = korean_chars + english_chars
    
    # 비율 계산
    special_char_ratio = special_chars / total_chars
    meaningful_char_ratio = meaningful_chars / total_chars
    
    # 유효성 검사 조건
    conditions = [
        # 1. 특수문자 비율이 30% 이하여야 함
        special_char_ratio <= 0.3,
        
        # 2. 의미있는 문자(한글/영문) 비율이 20% 이상이어야 함
        meaningful_char_ratio >= 0.2,
        
        # 3. 연속된 따옴표의 수가 전체 문자 수의 1% 이하여야 함
        consecutive_quotes <= (total_chars * 0.01),
        
        # 4. 따옴표의 수가 전체 문자 수의 10% 이하여야 함
        quotes_count <= (total_chars * 0.1)
    ]
    
    # 실패 이유 생성
    if not conditions[0]:
        return False, f"특수문자 비율이 너무 높음 ({special_char_ratio:.1%})"
    elif not conditions[1]:
        return False, f"의미있는 문자 비율이 너무 낮음 ({meaningful_char_ratio:.1%})"
    elif not conditions[2]:
        return False, f"연속된 따옴표가 너무 많음 ({consecutive_quotes}개)"
    elif not conditions[3]:
        return False, f"따옴표가 너무 많음 ({quotes_count}개)"
    
    return True, ""


def process_pdf(pdf_file_path: str, csv_writer: csv.DictWriter, 
                excluded_writer: csv.DictWriter, min_length: int = 30) -> bool:
    """PDF 파일에서 문장을 추출하여 CSV로 기록"""
    doc_id = os.path.splitext(os.path.basename(pdf_file_path))[0]
    doc = None
    
    try:
        # PDF 파일 열기 시도
        try:
            doc = fitz.open(pdf_file_path)
        except fitz.FileDataError:
            raise PDFProcessingError("손상된 PDF 파일")
        except Exception as e:
            raise PDFProcessingError(f"PDF 열기 실패: {str(e)}")
        
        logging.info(f"Processing {doc_id}: 총 페이지 수 = {len(doc)}")
        
        # 전체 문서 텍스트 추출
        full_text = ""
        for page in doc:
            text = safe_get_text(page)
            if text:
                full_text += clean_text(text) + "\n"
        
        # 문서 유효성 검사
        is_valid, reason = check_document_validity(full_text)
        if not is_valid:
            write_excluded_doc(excluded_writer, doc_id, reason)
            logging.info(f"Skipping {doc_id}: {reason}")
            return False
            
        # 문서가 유효한 경우 문장 추출 및 저장
        sentences_count = 0
        for page_no, page in enumerate(doc, 1):
            text = safe_get_text(page)
            if not text:
                continue

            try:
                text = clean_text(text)
                sentences = split_into_sentences(text)
                
                for i, sentence in enumerate(sentences):
                    if len(sentence) >= min_length:
                        try:
                            csv_writer.writerow({
                                'doc_id': doc_id,
                                'type': 'paper',
                                'page_no': page_no,
                                'sentence_no': i + 1,
                                'content': sentence
                            })
                            sentences_count += 1
                        except UnicodeEncodeError:
                            logging.warning(f"인코딩 오류 발생 - doc_id: {doc_id}, page: {page_no}")
                            continue
            except Exception as e:
                logging.warning(f"페이지 {page_no} 처리 중 오류: {str(e)}")
                continue

        if sentences_count == 0:
            reason = '추출된 문장이 없음'
            write_excluded_doc(excluded_writer, doc_id, reason)
            logging.info(f"Skipping {doc_id}: {reason}")
            return False

        logging.info(f"Completed {doc_id} - {sentences_count} sentences extracted")
        return True
    except PDFProcessingError as e:
        write_excluded_doc(excluded_writer, doc_id, str(e))
        logging.error(f"PDF 처리 오류 - {doc_id}: {str(e)}")
        return False
    except Exception as e:
        write_excluded_doc(excluded_writer, doc_id, '처리 중 예상치 못한 오류 발생', str(e))
        logging.error(f"예상치 못한 오류 - {doc_id}: {str(e)}")
        return False
    finally:
        if doc:
            try:
                doc.close()
            except Exception as e:
                logging.warning(f"PDF 파일 닫기 실패 - {doc_id}: {str(e)}")

def process_pdf_folder(folder_path: str, output_csv: str, min_length: int = 30) -> None:
    """폴더 내 PDF 파일을 일괄 처리하여 문장을 CSV에 기록"""
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {folder_path}")
    
    # 결과 저장할 디렉토리 생성
    output_dir = os.path.dirname(output_csv)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 제외된 문서 정보를 저장할 파일 경로
    excluded_csv = os.path.join(output_dir, '제외 문서.csv')
    
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    if not pdf_files:
        logging.warning(f"경고: {folder_path}에서 PDF 파일을 찾을 수 없습니다.")
        return
    
    logging.info(f"총 {len(pdf_files)}개의 PDF 파일을 처리합니다.")
    
    processed_docs = 0
    excluded_docs = 0
    
    try:
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as csvfile, \
             open(excluded_csv, 'w', newline='', encoding='utf-8-sig') as excluded_file:
            
            # 메인 CSV 작성기 설정
            fieldnames = ['doc_id', 'type', 'page_no', 'sentence_no', 'content']
            csv_writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            csv_writer.writeheader()
            
            # 제외된 문서 정보 CSV 작성기 설정
            excluded_fieldnames = ['doc_id', 'reason', 'error']
            excluded_writer = csv.DictWriter(excluded_file, fieldnames=excluded_fieldnames)
            excluded_writer.writeheader()
            
            # 각 PDF 파일 처리
            for filename in pdf_files:
                pdf_file_path = os.path.join(folder_path, filename)
                try:
                    if process_pdf(pdf_file_path, csv_writer, excluded_writer, min_length):
                        processed_docs += 1
                    else:
                        excluded_docs += 1
                except Exception as e:
                    logging.error(f"파일 처리 실패 - {filename}: {str(e)}")
                    excluded_docs += 1
                    continue
    
    except Exception as e:
        logging.error(f"CSV 파일 처리 중 오류 발생: {str(e)}")
        raise
    
    logging.info(f"\n처리 완료 통계:")
    logging.info(f"- 성공적으로 처리된 문서: {processed_docs}개")
    logging.info(f"- 제외된 문서: {excluded_docs}개")
    logging.info(f"- 총 처리 시도된 문서: {len(pdf_files)}개")
    logging.info(f"\n처리된 문장이 '{output_csv}'에 저장되었습니다.")
    logging.info(f"제외된 문서 정보가 '{excluded_csv}'에 저장되었습니다.")

if __name__ == "__main__":
    # 아래 path 경로 설정 필요 
    folder_path = "./data/paper"
    output_csv = './book/test/final_paper_Result.csv'
    min_sentence_length = 35
    
    try:
        process_pdf_folder(folder_path, output_csv, min_sentence_length)
    except Exception as e:
        logging.error(f"프로그램 실행 중 오류가 발생했습니다: {str(e)}")