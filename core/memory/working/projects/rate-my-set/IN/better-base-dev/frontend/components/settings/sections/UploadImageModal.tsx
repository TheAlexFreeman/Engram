import type { Area } from 'react-easy-crop';

import { useState } from 'react';

import { Box, DialogRootProps, HStack, Icon, Text, VStack } from '@chakra-ui/react';
import { FolderOpen as FolderIcon, Warning as WarningIcon } from '@phosphor-icons/react';
import Dropzone, { Accept, DropzoneOptions, type FileError } from 'react-dropzone';
import { Controller, FormProvider, useForm } from 'react-hook-form';

import {
  DialogBackdrop,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogHeader,
  DialogRoot,
} from '@/components/ui/dialog';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import { cropImage, validateImageDimensions } from '@/utils/images/cropping';
import { DEFAULT_PROFILE_IMAGE_CONFIG, type ProfileImageConfig } from '@/utils/images/imageConfig';

import ImageCropper from './ImageCropper';

export interface FormValueProps {
  file: File | null;
}

type UploadServiceCallFunction<T> = (file: File) => Promise<T>;

type UploadModalStep = 'selecting' | 'cropping' | 'uploading';

interface SelectedImage {
  file: File;
  url: string;
  dimensions: { width: number; height: number };
}

type Props<T> = {
  onUploadSubmit: UploadServiceCallFunction<T>;
  onCancel: () => void;
  onClose?: () => void;
  /** Optional config overrides for profile image settings. */
  imageConfig?: Partial<ProfileImageConfig>;
} & Omit<DialogRootProps, 'children'>;

export default function UploadImageModal<T>({
  onCancel,
  onClose,
  onUploadSubmit,
  imageConfig,
  ...rest
}: Props<T>) {
  const config = { ...DEFAULT_PROFILE_IMAGE_CONFIG, ...imageConfig };

  const [step, setStep] = useState<UploadModalStep>('selecting');
  const [selectedImage, setSelectedImage] = useState<SelectedImage | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const defaultValues = {
    file: null,
  };

  const methods = useForm<FormValueProps>({ defaultValues });

  const { control, reset, setError, clearErrors } = methods;

  const { BackendErrorsDisplay, errorWrappedRequest, setValidationError } =
    useHookFormBackendErrorsDisplay<FormValueProps>({ control });

  const cleanupAndClose = () => {
    if (selectedImage?.url) {
      URL.revokeObjectURL(selectedImage.url);
    }
    setSelectedImage(null);
    setStep('selecting');
    reset();
    setValidationError(null);
    onClose?.();
  };

  const handleBackToSelection = () => {
    if (selectedImage?.url) {
      URL.revokeObjectURL(selectedImage.url);
    }
    setSelectedImage(null);
    setStep('selecting');
    clearErrors();
  };

  const onDrop: DropzoneOptions['onDrop'] = async (acceptedFiles, fileRejections) => {
    if (isUploading || step === 'cropping') {
      return;
    }

    reset();
    clearErrors();

    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];

      try {
        // Validate dimensions against max upload dimension.
        const dimensions = await validateImageDimensions(file, config.maxUploadDimension);

        // Create object URL for cropper.
        const url = URL.createObjectURL(file);

        setSelectedImage({ file, url, dimensions });
        setStep('cropping');
      } catch (error) {
        setError('file', {
          message: error instanceof Error ? error.message : 'Failed to process image.',
        });
      }
    } else {
      const errorMessage = (fileRejections[0].errors as FileError[]).pop()?.message;
      if (errorMessage) {
        setError('file', { message: errorMessage });
      }
    }
  };

  const handleCropComplete = async (croppedAreaPixels: Area) => {
    if (!selectedImage) return;

    setStep('uploading');
    setIsUploading(true);

    try {
      const { file: croppedFile } = await cropImage(
        selectedImage.url,
        croppedAreaPixels,
        selectedImage.file.name,
        config.targetCropSize,
      );

      const wrapped = await errorWrappedRequest(onUploadSubmit(croppedFile));

      if (!wrapped.hasError) {
        cleanupAndClose();
      } else {
        // On upload failure, return to cropping step so user can retry.
        setStep('cropping');
      }
    } catch (error) {
      setError('file', {
        message: error instanceof Error ? error.message : 'Failed to crop image.',
      });
      setStep('cropping');
    } finally {
      setIsUploading(false);
    }
  };

  const handleCancel = () => {
    if (selectedImage?.url) {
      URL.revokeObjectURL(selectedImage.url);
    }
    setSelectedImage(null);
    setStep('selecting');
    onCancel();
    reset();
    setValidationError(null);
  };

  const acceptedImageTypes: Accept = {
    'image/*': [],
  };

  // Convert bytes to MB for display.
  const maxSizeMB = Math.round(config.maxFileSizeBytes / (1024 * 1024));

  return (
    <DialogRoot {...rest} onOpenChange={(e) => !e.open && cleanupAndClose()} size="xl">
      <DialogBackdrop />
      <DialogContent>
        <FormProvider {...methods}>
          <DialogHeader>{step === 'cropping' ? 'Crop image' : 'Upload image'}</DialogHeader>
          <DialogCloseTrigger onClick={handleCancel} />
          <DialogBody>
            {step === 'selecting' && (
              <Controller
                name="file"
                control={control}
                render={({ fieldState: { error } }) => (
                  <>
                    <Dropzone
                      accept={acceptedImageTypes}
                      onDrop={onDrop}
                      minSize={0}
                      maxSize={config.maxFileSizeBytes}
                      maxFiles={1}
                    >
                      {({ getRootProps, getInputProps }) => (
                        <Box
                          width="full"
                          backgroundColor="bg.level1"
                          display="flex"
                          justifyContent="center"
                          alignItems="center"
                          borderRadius="lg"
                          p={10}
                          mb={2}
                          cursor="pointer"
                        >
                          <div {...getRootProps()}>
                            <input {...getInputProps()} />
                            <HStack gap={8} mb={8}>
                              <Icon color="primary.bg.main" fontSize="9xl">
                                <FolderIcon weight="fill" />
                              </Icon>
                              <VStack>
                                <Text textStyle="h3">Drag and drop a file</Text>
                                <HStack gap={0.5}>
                                  <Text textStyle="h5">Or </Text>
                                  <Text textStyle="h5" color="text.link">
                                    {' '}
                                    select a file
                                  </Text>
                                </HStack>
                              </VStack>
                            </HStack>

                            <Text textStyle="body3" color="text.lighter">
                              Must be a picture file under {maxSizeMB} MB. Large images will be
                              cropped.
                            </Text>
                          </div>
                        </Box>
                      )}
                    </Dropzone>
                    {error && (
                      <HStack color="red.600">
                        <Icon>
                          <WarningIcon weight="fill" />
                        </Icon>
                        <Text textStyle="body3">{error.message}</Text>
                      </HStack>
                    )}
                  </>
                )}
              />
            )}

            {(step === 'cropping' || step === 'uploading') && selectedImage && (
              <ImageCropper
                imageSrc={selectedImage.url}
                config={config}
                onCropComplete={handleCropComplete}
                onBack={handleBackToSelection}
                isProcessing={isUploading}
              />
            )}

            <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
          </DialogBody>
        </FormProvider>
      </DialogContent>
    </DialogRoot>
  );
}
