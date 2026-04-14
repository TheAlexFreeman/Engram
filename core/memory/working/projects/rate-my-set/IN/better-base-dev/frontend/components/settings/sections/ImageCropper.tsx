import type { Area, Point } from 'react-easy-crop';

import { useCallback, useState } from 'react';

import { Box, HStack, Icon, Text, VStack } from '@chakra-ui/react';
import { MagnifyingGlassMinus, MagnifyingGlassPlus } from '@phosphor-icons/react';
import Cropper from 'react-easy-crop';

import type { ProfileImageConfig } from '@/utils/images/imageConfig';

import { Button } from '@/components/ui/button';

interface ImageCropperProps {
  /** Source image URL to crop. */
  imageSrc: string;
  /** Configuration for cropping behavior. */
  config: ProfileImageConfig;
  /** Callback when crop is confirmed with the pixel crop area. */
  onCropComplete: (croppedAreaPixels: Area) => void;
  /** Callback when user wants to go back to file selection. */
  onBack: () => void;
  /** Whether the cropper is in a loading/processing state. */
  isProcessing?: boolean;
}

export default function ImageCropper({
  imageSrc,
  config,
  onCropComplete,
  onBack,
  isProcessing = false,
}: ImageCropperProps) {
  const [crop, setCrop] = useState<Point>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);

  const handleCropComplete = useCallback((_croppedArea: Area, nextCroppedAreaPixels: Area) => {
    setCroppedAreaPixels(nextCroppedAreaPixels);
  }, []);

  const handleConfirm = () => {
    if (croppedAreaPixels) {
      onCropComplete(croppedAreaPixels);
    }
  };

  const handleZoomChange = (newZoom: number) => {
    setZoom(Math.min(config.maxZoom, Math.max(config.minZoom, newZoom)));
  };

  return (
    <VStack gap={4} width="full">
      {/* Cropper container */}
      <Box
        position="relative"
        width="full"
        height="300px"
        backgroundColor="bg.level1"
        borderRadius="lg"
        overflow="hidden"
      >
        <Cropper
          image={imageSrc}
          crop={crop}
          zoom={zoom}
          aspect={1}
          cropShape="round"
          showGrid={false}
          onCropChange={setCrop}
          onZoomChange={setZoom}
          onCropComplete={handleCropComplete}
        />
      </Box>

      {/* Zoom slider */}
      <HStack width="full" gap={3} px={4}>
        <Icon color="text.lighter" fontSize="lg">
          <MagnifyingGlassMinus />
        </Icon>
        <Box flex={1}>
          <input
            type="range"
            min={config.minZoom}
            max={config.maxZoom}
            step={config.zoomStep}
            value={zoom}
            onChange={(e) => handleZoomChange(parseFloat(e.target.value))}
            style={{
              width: '100%',
              accentColor: 'var(--chakra-colors-primary-bg-main)',
            }}
          />
        </Box>
        <Icon color="text.lighter" fontSize="lg">
          <MagnifyingGlassPlus />
        </Icon>
      </HStack>

      <Text textStyle="body3" color="text.lighter" textAlign="center">
        Drag to reposition. Use the slider to zoom.
      </Text>

      {/* Action buttons */}
      <HStack width="full" justifyContent="space-between" pt={2}>
        <Button
          variant="outline"
          borderColor="bg.level3"
          borderWidth={2}
          color="text.main"
          onClick={onBack}
          disabled={isProcessing}
        >
          Back
        </Button>
        <Button
          onClick={handleConfirm}
          loading={isProcessing}
          disabled={!croppedAreaPixels || isProcessing}
        >
          Crop & Save
        </Button>
      </HStack>
    </VStack>
  );
}
