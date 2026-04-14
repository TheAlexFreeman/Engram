import { useCallback, useEffect, useMemo, useState } from 'react';

import { Icon, Input, InputProps, chakra } from '@chakra-ui/react';
import { useDebounce } from 'use-debounce';

import SearchIcon from '@/assets/custom-icons/SearchIcon';

import { InputGroup, type InputGroupProps } from '../ui/input-group';

type SearchInputType = { q?: string };
type UpdateSearchType = (update: Partial<SearchInputType>) => void;

type SearchInputProps<SearchT extends SearchInputType> = {
  search: SearchT;
  updateSearch: UpdateSearchType;
  inputGroupProps?: Partial<Omit<InputGroupProps, 'children' | 'startElement'>>;
} & InputProps;

export default function SearchInput<SearchT extends SearchInputType>({
  search,
  updateSearch,
  inputGroupProps,
  ...rest
}: SearchInputProps<SearchT>) {
  const [hasFocus, setHasFocus] = useState(false);

  const setFocus = useCallback(() => setHasFocus(true), []);
  const setBlur = useCallback(() => setHasFocus(false), []);

  const inputProps = useMemo(() => {
    const props = { ...rest };

    if (!props.placeholder) {
      props.placeholder = 'Search';
    }

    props.onFocus = setFocus;
    props.onBlur = setBlur;

    return props;
  }, [rest, setBlur, setFocus]);

  const [inputValue, setInputValue] = useState(search.q || '');
  const onChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  }, []);

  const [debouncedValue, { flush }] = useDebounce(inputValue, 350);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        flush();
      }
    },
    [flush],
  );

  useEffect(() => {
    if (debouncedValue !== (search.q || '')) {
      updateSearch({ q: debouncedValue });
    }
  }, [debouncedValue, search.q, updateSearch]);

  const iconOffset = useMemo(() => {
    if (inputProps.size === 'sm') return -2;
    if (inputProps.size === 'lg') return 1.5;
    return 0;
  }, [inputProps.size]);

  const SearchInputIcon = useCallback(
    () => <SearchIcon color={hasFocus ? 'primary.bg.main' : 'text.lighter'} />,
    [hasFocus],
  );

  return (
    <InputGroup
      {...inputGroupProps}
      startElement={
        <chakra.span mt={iconOffset}>
          <Icon as={SearchInputIcon} />
        </chakra.span>
      }
    >
      <Input {...inputProps} value={inputValue} onChange={onChange} onKeyDown={onKeyDown} />
    </InputGroup>
  );
}
