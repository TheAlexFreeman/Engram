from __future__ import annotations

from PIL import Image


def process_profile_image(image_path, output_path) -> None:
    crop_center(image_path, output_path + "Small.png", (128, 128))
    crop_center(image_path, output_path + "Med.png", (256, 256))
    crop_center(image_path, output_path + "Large.png", (512, 512))


def crop_center(image_path, output_path, crop_size=(128, 128)):
    with Image.open(image_path) as img:
        # Calculate the coordinates for a center crop
        width, height = img.size
        left = (width - crop_size[0]) / 2
        top = (height - crop_size[1]) / 2
        right = (width + crop_size[0]) / 2
        bottom = (height + crop_size[1]) / 2

        # Crop the center of the image
        img_cropped = img.crop((left, top, right, bottom))

        # Save or process the cropped image
        img_cropped.save(output_path, "PNG")
        return img_cropped


def create_thumbnail(image_path, output_path, size=(128, 128)):
    with Image.open(image_path) as img:
        img.thumbnail(size)
        img.save(output_path, "PNG")
