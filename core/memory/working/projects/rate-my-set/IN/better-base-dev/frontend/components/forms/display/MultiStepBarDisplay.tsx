import { Box, HStack, StackProps } from '@chakra-ui/react';

export type MultiStepBarDisplayProps = {
  currentNum: number;
  totalNum: number;
} & StackProps;

export default function MultiStepBarDisplay({
  currentNum,
  totalNum,
  ...rest
}: MultiStepBarDisplayProps) {
  return (
    <HStack gap="1" {...rest}>
      {Array.from({ length: totalNum }).map((_, i) => {
        return (
          <Box
            key={i}
            css={{
              height: '0.25rem',
              width: '12',
              bgColor: 'bg.level2',
              borderRadius: 'md',
              ...(i < currentNum
                ? {
                    bgColor: 'primary.text.main',
                  }
                : {}),
            }}
          />
        );
      })}
    </HStack>
  );
}
