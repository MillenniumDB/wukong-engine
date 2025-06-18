import base64
import concurrent.futures
import os

import requests
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image

from .image_to_text_utils import ImageToTextUtils

# TODO: Refactor everything in this module later

load_dotenv('.env')
api_key = os.getenv('OPENAI_API_KEY')
gpt_model = 'gpt-4.1'
scale_low_to_tiles = None
scale_high_to_tiles = 3

TILE_SIZE = 512


def encode_image(image_path):
    """
    Encode an image at the given path to a base64 string.
    """

    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def pdf_to_images(
    pdf_path, images_folder, scale_high_to_tiles: int | None = None, scale_low_to_tiles: int | None = None
):
    """
    Converts a PDF to a list of images, using the given scale factors to control the size of the output images.

    Args:
        pdf_path (str): The path to the PDF file.
        images_folder (str): The folder to save the generated images in.
        scale_high_to_tiles (int|None): If set to a positive value, the output images will be scaled so that the larger dimension is this many tiles.
        scale_low_to_tiles (int|None): If set to a positive value, the output images will be scaled so that the smaller dimension is this many tiles.

    Returns:
        list[str]: A list of paths to the generated images.
    """

    image_to_text_utils = ImageToTextUtils()

    images = convert_from_path(pdf_path)
    image_paths = []
    for i, image in enumerate(images):
        scaling_factor = 1
        width, height = image.size
        if scale_high_to_tiles is not None and scale_high_to_tiles > 0:
            scaling_factor = scale_high_to_tiles * TILE_SIZE / max(width, height)
        elif scale_low_to_tiles is not None and scale_low_to_tiles > 0:
            scaling_factor = scale_low_to_tiles * TILE_SIZE / min(width, height)

        if scaling_factor < 1:
            new_size = (int(width * scaling_factor), int(height * scaling_factor))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        image_path = os.path.join(images_folder, f'page_{i + 1}.png')
        image.save(image_path, 'PNG')
        image_to_text_utils.find_best_orientation(image_path, image_path, verbose=False)
        image_paths.append(image_path)
    return image_paths


def extract_text_from_images(image_paths, temp_output_folder, retries=3, timeout=120):
    """
    Extracts text from the given list of image paths using the OpenAI OCR API.

    Args:
        image_paths (list[str]): The list of image paths to extract text from.
        temp_output_folder (str): The folder to save temporary results in.
        retries (int, optional): The number of times to retry the extraction process if it fails. Defaults to 3.
        timeout (int, optional): The timeout in seconds for the extraction process. Defaults to 120.

    Returns:
        list[str]: The list of extracted text strings, in the same order as the input image paths.
    """

    def extract_text(image_path):
        """
        Extracts text from a single image using the OpenAI OCR API.

        Args:
            image_path (str): The path to the image to extract text from.

        Returns:
            str: The extracted text string.
        """
        raw_temp_text_file_path = os.path.join(
            temp_output_folder, os.path.splitext(os.path.basename(image_path))[0] + '_raw' + '.txt'
        )
        temp_text_file_path = os.path.join(
            temp_output_folder, os.path.splitext(os.path.basename(image_path))[0] + '.txt'
        )
        if os.path.exists(temp_text_file_path):
            with open(temp_text_file_path, 'r', encoding='utf-8') as temp_file:
                text = temp_file.read()
                return text
        else:
            base64_image = encode_image(image_path)
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}

            text_content = ''
            for attempt in range(retries):
                payload = {
                    'model': gpt_model,
                    'messages': [
                        {
                            'role': 'user',
                            'content': [
                                {
                                    'type': 'text',
                                    'text': "Extract as much text as possible from this image. The image may be a scanned document with varying contrast, handwritten text, stains, or bleed-through from text on the reverse side. Adjust the image's contrast multiple times to identify the best setting to improve extraction accuracy and ignore text on the reverse side. Fix any obvious typos in the text, but avoid including any special formatting characters such as '**', '_', or similar. Ensure that numbers and dashes in lists are preserved and formatted clearly. For sections of the image where text extraction is not possible, use '[...]' as a placeholder. If any errors occur during extraction, respond only with 'OCR ERROR' followed by a brief explanation of the issue. In that case, make sure not to omit 'OCR ERROR' because the error will be parsed automatically.",
                                },
                                {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{base64_image}'}},
                            ],
                        }
                    ],
                    'max_tokens': 4096,
                }
                try:
                    response = requests.post(
                        'https://api.openai.com/v1/chat/completions', headers=headers, json=payload, timeout=timeout
                    )
                    response.raise_for_status()
                    result = response.json()
                    if result['choices'][0]['message']['content'].startswith('OCR ERROR'):
                        error_message = result['choices'][0]['message']['content']
                        raise Exception(f'Failed to extract text. {error_message}')
                    text_content = result['choices'][0]['message']['content']

                    with open(raw_temp_text_file_path, 'w', encoding='utf-8') as temp_file:
                        temp_file.write(text_content)
                    break
                except Exception as error:
                    print(f'OCR attempt {attempt + 1} failed with error: {error}')
                    if attempt + 1 == retries:
                        text_placeholder = '...'
                        with open(raw_temp_text_file_path, 'w', encoding='utf-8') as temp_file:
                            temp_file.write(text_placeholder)
                        with open(temp_text_file_path, 'w', encoding='utf-8') as temp_file:
                            temp_file.write(text_placeholder)
                        # raise e
                        return text_placeholder
                    print('Retrying...')

            for attempt in range(retries):
                payload = {
                    'model': gpt_model,
                    'messages': [
                        {
                            'role': 'user',
                            'content': [
                                {
                                    'type': 'text',
                                    'text': 'You will be given a piece of text extracted from an image. You need to solve existing typos and name inconsistencies in the text and return only the correct text. Please do not add any additional messages to the response.',
                                },
                                {'type': 'text', 'text': text_content},
                            ],
                        }
                    ],
                    'max_tokens': 4096,
                }
                try:
                    response = requests.post(
                        'https://api.openai.com/v1/chat/completions', headers=headers, json=payload, timeout=timeout
                    )
                    response.raise_for_status()
                    result = response.json()
                    fixed_text_content = result['choices'][0]['message']['content']

                    with open(temp_text_file_path, 'w', encoding='utf-8') as temp_file:
                        temp_file.write(fixed_text_content)

                    return fixed_text_content
                except Exception as error:
                    print(f'Typos fix attempt {attempt + 1} failed with error: {error}')
                    if attempt + 1 == retries:
                        raise error
                    print('Retrying...')

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(extract_text, image_path): image_path for i, image_path in enumerate(image_paths)}
        results = [None] * len(image_paths)
        try:
            for future in concurrent.futures.as_completed(futures):
                image_path = futures[future]
                index = image_paths.index(image_path)
                try:
                    result = future.result()
                    results[index] = result
                except Exception as error:
                    print(f'Error occurred during execution: {error}')
                    for future in futures:
                        future.cancel()
                    raise error
        except Exception as error:
            print(f'An error occurred: {error}')

            for future in futures:
                future.cancel()
            raise error

    return results


def process_all_pdfs_in_folder(pdf_folder, output_folder):
    """
    Process all PDF files in a given folder and save the extracted text to a given output folder.

    Args:
        pdf_folder (str): The folder containing the PDF files to process.
        output_folder (str): The folder where the extracted text files will be saved.
    """
    os.makedirs(output_folder, exist_ok=True)

    for pdf_filename in os.listdir(pdf_folder):
        if pdf_filename.lower().endswith('.pdf'):
            text_filename = os.path.splitext(pdf_filename)[0] + '.txt'
            text_file_path = os.path.join(output_folder, text_filename)

            if os.path.exists(text_file_path):
                print(f'Text file {text_file_path} already exists. Skipping {pdf_filename}.')
                continue

            pdf_path = os.path.join(pdf_folder, pdf_filename)

            temp_output_folder = os.path.join(output_folder, f'{os.path.splitext(pdf_filename)[0]}_temp')
            temp_images_folder = os.path.join(temp_output_folder, 'images')
            temp_texts_folder = os.path.join(temp_output_folder, 'texts')
            os.makedirs(temp_output_folder, exist_ok=True)
            os.makedirs(temp_images_folder, exist_ok=True)
            os.makedirs(temp_texts_folder, exist_ok=True)

            try:
                image_paths = pdf_to_images(
                    pdf_path=pdf_path,
                    images_folder=temp_images_folder,
                    scale_high_to_tiles=scale_high_to_tiles,
                    scale_low_to_tiles=scale_low_to_tiles,
                )
                texts = extract_text_from_images(image_paths, temp_texts_folder, timeout=60)
                all_text = '\n\n'.join(texts)

                with open(text_file_path, 'w', encoding='utf-8') as text_file:
                    text_file.write(all_text)

                for temp_file in os.listdir(temp_texts_folder):
                    os.remove(os.path.join(temp_texts_folder, temp_file))
                os.rmdir(temp_texts_folder)

                for temp_file in os.listdir(temp_images_folder):
                    os.remove(os.path.join(temp_images_folder, temp_file))
                os.rmdir(temp_images_folder)

                for temp_file in os.listdir(temp_output_folder):
                    os.remove(os.path.join(temp_output_folder, temp_file))
                os.rmdir(temp_output_folder)

                print(f'Text extracted from {pdf_filename} and saved to {text_file_path}.')
            except Exception as error:
                print(f'An error occurred while processing {pdf_filename}: {error}')
                continue
