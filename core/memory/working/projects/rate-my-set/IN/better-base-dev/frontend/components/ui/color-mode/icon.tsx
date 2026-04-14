'use client';

import { LuMoon, LuSun } from 'react-icons/lu';

import { useColorMode } from './hooks';

export function ColorModeIcon() {
  const { colorMode } = useColorMode();
  return colorMode === 'light' ? <LuSun /> : <LuMoon />;
}
