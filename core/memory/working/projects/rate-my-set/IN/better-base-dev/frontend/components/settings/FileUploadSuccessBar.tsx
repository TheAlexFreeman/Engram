import { HStack, IconButton, Spacer, Text } from '@chakra-ui/react';
import { Trash as TrashIcon } from '@phosphor-icons/react';

type Props = {
  beginningText: string;
  endText: string;
  onDelete: () => void;
};

export default function FileUploadSuccessBar({ beginningText, endText, onDelete }: Props) {
  const handleDeleteClick = () => {
    onDelete();
  };
  return (
    <HStack background="primary.bg.light" borderRadius={16} py={1.5} px={3}>
      <Text textStyle="body2">{beginningText}</Text>
      <Spacer />
      <Text textStyle="body2">{endText}</Text>
      <IconButton
        aria-label="Remove profile image"
        color={'primary.bg.main'}
        onClick={handleDeleteClick}
        backgroundColor="transparent"
        _hover={{ cursor: 'pointer', color: 'primary.bg.contrast' }}
        _active={{ bg: 'transparent' }}
      >
        <TrashIcon weight="fill" />
      </IconButton>
    </HStack>
  );
}
