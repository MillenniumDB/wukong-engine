import cv2
import pytesseract
from nltk.corpus import cess_esp, words

# TODO: Refactor everything in this module later


class ImageToTextUtils:
    """Provides utilities for detecting coherent English and Spanish words in images using OCR, rotating images to find the best orientation, and saving the correctly oriented image"""

    WORD_LENGTH_THRESHOLD = 30

    def __init__(self):
        self.english_words = set(words.words())
        self.spanish_words = set(cess_esp.words())

    def detect_coherent_words(self, image):
        """
        Detect text in the image, split it into words, and calculate the sum of the lengths of valid English and Spanish words.
        Only considers words with length greater than 3.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(gray, config=custom_config)

        detected_words = text.split()

        total_length = sum(
            len(word)
            for word in detected_words
            if len(word) > 3 and (word.lower() in self.english_words or word.lower() in self.spanish_words)
        )

        return total_length, text.strip()

    def rotate_image(image, angle):
        """
        Rotate the image by the specified angle.
        """
        (h, w) = image.shape[:2]

        center = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D(center, -angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h))

        return rotated

    def find_best_orientation(self, image_path, output_path, verbose=True):
        """
        Rotate the image in 0°, 90°, 180°, and 270°, detect the coherent words for each,
        and choose the orientation that recognizes the most coherent text based on total length.
        """

        image = cv2.imread(image_path)

        angles = [0, 90, 180, 270]
        best_angle = 0
        max_total_length = 0
        best_text = ''

        for angle in angles:
            rotated_image = ImageToTextUtils.rotate_image(image, angle)
            total_length, detected_text = self.detect_coherent_words(rotated_image)
            if verbose:
                print(f'Total length of coherent words at {angle}°: {total_length}')
                print(f'Detected text: {detected_text[:100]}...')

            if total_length > max_total_length:
                max_total_length = total_length
                best_angle = angle
                best_text = detected_text

        if max_total_length < ImageToTextUtils.WORD_LENGTH_THRESHOLD:
            if verbose:
                print(
                    f'Total length of coherent words is less than {ImageToTextUtils.WORD_LENGTH_THRESHOLD}, skipping image'
                )
            return

        if verbose:
            print(f'Best angle: {best_angle}° with {max_total_length} total length of coherent words')
            print(f'Detected text at best angle: {best_text}')

        if best_angle != 0:
            print(f'Image {image_path} was rotated by {best_angle}°')

        correctly_oriented_image = ImageToTextUtils.rotate_image(image, best_angle)
        cv2.imwrite(output_path, correctly_oriented_image)
        if verbose:
            print(f'Image saved at: {output_path}')
