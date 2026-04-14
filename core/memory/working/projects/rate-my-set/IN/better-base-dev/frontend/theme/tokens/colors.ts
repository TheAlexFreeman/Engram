import { defineTokens } from '@chakra-ui/react';

const grayAndOrNeutral = {
  '50': { value: '#F5F5F5' },
  '100': { value: '#E3E4E5' },
  '200': { value: '#BFC0C7' },
  '300': { value: '#AAABB2' },
  '400': { value: '#909199' },
  '500': { value: '#71727A' },
  '600': { value: '#5D5E67' },
  '700': { value: '#43454D' },
  '800': { value: '#2C2E34' },
  '900': { value: '#181A1F' },
  // CV3M TODO: Add 950
  '950': { value: '#181A1F' },
};

const black = {
  value: '#141414',
};

const white = {
  value: '#FFFFFF',
};

const lightBlue = {
  '50': { value: '#EFF9FC' },
  '100': { value: '#E1F4FA' },
  '200': { value: '#ACE7DB' },
  '300': { value: '#95E1F8' },
  '400': { value: '#6FC5DF' },
  '500': { value: '#50ADC9' },
  '600': { value: '#328BA6' },
  '700': { value: '#065470' },
  '800': { value: '#11394A' },
  '900': { value: '#052634' },
  // CV3M TODO: Add 950
  '950': { value: '#052634' },
};

export const colors = defineTokens.colors({
  black,
  white,
  common: {
    black,
    white,
  },
  // NOTE: At the time of writing, we have used gray (Chakra terminology) and neutral
  // (our terminology) interchangeably (for the most part), so we'll define them both to
  // point to the same color palette.
  gray: grayAndOrNeutral,
  neutral: grayAndOrNeutral,
  purple: {
    '50': { value: '#F0F0FF' },
    '100': { value: '#DBDAF7' },
    '200': { value: '#B9B7ED' },
    '300': { value: '#8986E0' },
    '400': { value: '#6C67D9' },
    '500': { value: '#4E49D1' },
    '600': { value: '#413DAE' },
    '700': { value: '#34318B' },
    '800': { value: '#272569' },
    '900': { value: '#1A1846' },
    // CV3M TODO: Add 950
    '950': { value: '#1A1846' },
  },
  green: {
    '50': { value: '#E9F7F5' },
    '100': { value: '#CFF6EF' },
    '200': { value: '#B6E2F0' },
    '300': { value: '#9AD6CA' },
    '400': { value: '#72D0BD' },
    '500': { value: '#12BB99' },
    '600': { value: '#00A383' },
    '700': { value: '#006752' },
    '800': { value: '#004537' },
    '900': { value: '#003329' },
    // CV3M TODO: Add 950
    '950': { value: '#003329' },
  },
  // NOTE: At the time of writing, we have used blue (Chakra terminology) and lightBlue
  // (our terminology) interchangeably (for the most part), so we'll define them both to
  // point to the same color palette.
  blue: lightBlue,
  lightBlue,
  yellow: {
    '50': { value: '#FFFBCC' },
    '100': { value: '#FFF7A8' },
    '200': { value: '#FAEF7F' },
    '300': { value: '#F1E455' },
    '400': { value: '#EEDD2A' },
    '500': { value: '#F3DF00' },
    '600': { value: '#D3C31B' },
    '700': { value: '#9F9100' },
    '800': { value: '#6F6608' },
    '900': { value: '#2F2B00' },
    // CV3M TODO: Add 950
    '950': { value: '#2F2B00' },
  },
  red: {
    '50': { value: '#FFEBEC' },
    '100': { value: '#FFD3D3' },
    '200': { value: '#FFA8A5' },
    '300': { value: '#FFA8A5' },
    '400': { value: '#FA5255' },
    '500': { value: '#DB3142' },
    '600': { value: '#BB1C33' },
    '700': { value: '#821A26' },
    '800': { value: '#580013' },
    '900': { value: '#39000D' },
    // CV3M TODO: Add 950
    '950': { value: '#39000D' },
  },
});
