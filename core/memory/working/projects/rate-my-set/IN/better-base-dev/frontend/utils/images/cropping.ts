import type { Area } from 'react-easy-crop';

import { DEFAULT_PROFILE_IMAGE_CONFIG } from './imageConfig';

export interface CropResult {
  file: File;
  url: string;
}

export interface ImageDimensions {
  width: number;
  height: number;
}

/**
 * Creates a cropped image from the source image and crop area.
 *
 * @param imageSrc - The source image URL (object URL or data URL).
 * @param cropArea - The pixel coordinates and dimensions of the crop area.
 * @param originalFileName - Original file name for generating cropped filename.
 * @param targetSize - Target output size (default from config).
 * @returns Promise resolving to the cropped file and its object URL.
 */
export async function cropImage(
  imageSrc: string,
  cropArea: Area,
  originalFileName: string,
  targetSize: number = DEFAULT_PROFILE_IMAGE_CONFIG.targetCropSize,
): Promise<CropResult> {
  const image = await createImage(imageSrc);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');

  if (!ctx) {
    throw new Error('Failed to get canvas context.');
  }

  // Determine output size: use target size or smaller dimension if source crop is smaller.
  const outputSize = Math.min(targetSize, cropArea.width, cropArea.height);

  canvas.width = outputSize;
  canvas.height = outputSize;

  // Draw the cropped and scaled image.
  ctx.drawImage(
    image,
    cropArea.x,
    cropArea.y,
    cropArea.width,
    cropArea.height,
    0,
    0,
    outputSize,
    outputSize,
  );

  // Generate the cropped filename.
  const croppedFileName = nameCroppedImage(originalFileName, outputSize);

  // Convert canvas to blob and create file.
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error('Failed to create image blob.'));
          return;
        }

        const file = new File([blob], croppedFileName, {
          type: 'image/jpeg',
          lastModified: Date.now(),
        });

        const url = URL.createObjectURL(file);
        resolve({ file, url });
      },
      'image/jpeg',
      0.9, // Quality setting for JPEG.
    );
  });
}

/**
 * Creates an HTMLImageElement from a source URL.
 */
function createImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener('load', () => resolve(image));
    image.addEventListener('error', (error) => reject(error));
    image.src = src;
  });
}

/**
 * Generates a cropped filename following the pattern: `{original}_c_{size}x{size}.jpg`.
 */
export function nameCroppedImage(originalFileName: string, size: number): string {
  const lastDotIndex = originalFileName.lastIndexOf('.');
  const baseName = lastDotIndex > 0 ? originalFileName.slice(0, lastDotIndex) : originalFileName;
  // Always output as JPEG for consistency.
  return `${baseName}_c_${size}x${size}.jpg`;
}

/**
 * Validates image dimensions against the maximum allowed dimension.
 *
 * @param file - The image file to validate.
 * @param maxDimension - Maximum allowed dimension (default from config).
 * @returns Promise resolving to dimensions if valid, or rejecting with error message.
 */
export async function validateImageDimensions(
  file: File,
  maxDimension: number = DEFAULT_PROFILE_IMAGE_CONFIG.maxUploadDimension,
): Promise<ImageDimensions> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();

    image.onload = () => {
      URL.revokeObjectURL(url);

      if (image.width > maxDimension || image.height > maxDimension) {
        reject(
          new Error(
            `Image dimensions exceed ${maxDimension}x${maxDimension}. ` +
              `Your image is ${image.width}x${image.height}.`,
          ),
        );
        return;
      }

      resolve({ width: image.width, height: image.height });
    };

    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load image for validation.'));
    };

    image.src = url;
  });
}
