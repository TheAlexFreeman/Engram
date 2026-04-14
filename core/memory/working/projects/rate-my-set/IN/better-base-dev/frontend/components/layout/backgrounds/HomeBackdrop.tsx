import { Box, BoxProps } from '@chakra-ui/react';

import blurFullUrl from '@/assets/backgrounds/BackgroundHomeBlurFull.png';
import blurSideUrl from '@/assets/backgrounds/BackgroundHomeBlurSide.png';
import imageFullUrl from '@/assets/backgrounds/BackgroundHomeImageFull.png';
import imageSideUrl from '@/assets/backgrounds/BackgroundHomeImageSide.png';
import { useColorMode } from '@/components/ui/color-mode';

export type HomeBackdropProps = BoxProps & {
  size: 'full' | 'side';
  variant?: 'blur' | 'image' | undefined;
};

export default function HomeBackdrop({ size, variant, ...rest }: HomeBackdropProps) {
  const { colorMode } = useColorMode();
  const defaultVariant = colorMode == 'dark' ? 'image' : 'blur';
  const variantToUse = variant || defaultVariant;

  let backdropUrl: string;
  if (size === 'full' && variantToUse === 'blur') {
    backdropUrl = blurFullUrl;
  } else if (size === 'full' && variantToUse === 'image') {
    backdropUrl = imageFullUrl;
  } else if (size === 'side' && variantToUse === 'blur') {
    backdropUrl = blurSideUrl;
  } else {
    backdropUrl = imageSideUrl;
  }

  const boxProps = { ...(rest || {}) };

  if (!boxProps.bgSize) {
    boxProps.bgSize = 'cover';
  }
  if (!boxProps.bgRepeat) {
    boxProps.bgRepeat = 'no-repeat';
  }

  return <Box backgroundImage={`url(${backdropUrl})`} {...boxProps} />;
}
