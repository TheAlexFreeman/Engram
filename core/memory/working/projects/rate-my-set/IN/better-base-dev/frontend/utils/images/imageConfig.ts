/**
 * Configuration for profile image uploads and cropping.
 */
export interface ProfileImageConfig {
  /** Maximum dimension (width or height) allowed for uploaded images. */
  maxUploadDimension: number;
  /** Target output size for cropped images (square). */
  targetCropSize: number;
  /** Maximum file size in bytes for uploads. */
  maxFileSizeBytes: number;
  /** Minimum zoom level for cropper. */
  minZoom: number;
  /** Maximum zoom level for cropper. */
  maxZoom: number;
  /** Zoom step for slider. */
  zoomStep: number;
}

export const DEFAULT_PROFILE_IMAGE_CONFIG: ProfileImageConfig = {
  maxUploadDimension: 16384,
  targetCropSize: 1024,
  maxFileSizeBytes: 3_000_000, // 3MB (SI units)
  minZoom: 1,
  maxZoom: 3,
  zoomStep: 0.1,
};

/**
 * Creates a profile image config with optional overrides.
 */
export function createProfileImageConfig(
  overrides?: Partial<ProfileImageConfig>,
): ProfileImageConfig {
  return { ...DEFAULT_PROFILE_IMAGE_CONFIG, ...overrides };
}
