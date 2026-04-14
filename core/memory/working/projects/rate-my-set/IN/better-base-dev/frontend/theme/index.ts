import { createSystem, defaultConfig } from '@chakra-ui/react';

import { globalCss } from './global-css';
import { buttonRecipe } from './recipes/button';
import { colors as semanticColors } from './semantic-tokens/colors';
import { shadows as semanticShadows } from './semantic-tokens/shadows';
import { textStyles } from './text-styles';
import { colors } from './tokens/colors';
import { fontSizes } from './tokens/font-sizes';
import { fontWeights } from './tokens/font-weights';
import { fonts } from './tokens/fonts';
import { letterSpacings } from './tokens/letter-spacings';
import { lineHeights } from './tokens/line-heights';
import { radii } from './tokens/radii';

export const system = createSystem(defaultConfig, {
  cssVarsPrefix: 'chakra',
  globalCss: globalCss,
  strictTokens: false,
  theme: {
    recipes: {
      button: buttonRecipe,
    },
    semanticTokens: {
      colors: semanticColors,
      shadows: semanticShadows,
    },
    textStyles: textStyles,
    tokens: {
      colors: colors,
      fontSizes: fontSizes,
      fontWeights: fontWeights,
      fonts: fonts,
      letterSpacings: letterSpacings,
      lineHeights: lineHeights,
      radii: radii,
    },
  },
});
