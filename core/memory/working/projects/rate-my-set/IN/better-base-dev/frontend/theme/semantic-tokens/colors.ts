import { defineSemanticTokens } from '@chakra-ui/react';

const defaultFocusToken = {
  value: {
    base: 'rgba(9, 0, 244, 0.27)',
    _dark: 'rgba(130, 124, 255, 0.65)',
  },
};

export const colors = defineSemanticTokens.colors({
  // Newer Chakra V3 semantic token of `focusRing`.
  focusRing: defaultFocusToken,
  // Our own semantic token of `focus`.
  focus: defaultFocusToken,
  //
  // - https://www.chakra-ui.com/docs/theming/colors#semantic-tokens
  //   - background
  bg: {
    // Newer Chakra V3 semantic tokens.
    DEFAULT: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.neutral.900}',
      },
    },
    subtle: {
      value: {
        base: '{colors.neutral.50}',
        _dark: '{colors.neutral.950}',
      },
    },
    muted: {
      value: {
        base: '{colors.neutral.100}',
        _dark: '{colors.neutral.900}',
      },
    },
    emphasized: {
      value: {
        base: '{colors.neutral.200}',
        _dark: '{colors.neutral.800}',
      },
    },
    inverted: {
      value: {
        base: '{colors.common.black}',
        _dark: '{colors.common.white}',
      },
    },
    panel: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.neutral.950}',
      },
    },
    error: {
      value: {
        base: '{colors.red.50}',
        _dark: '{colors.red.950}',
      },
    },
    warning: {
      value: {
        base: '{colors.yellow.50}',
        _dark: '{colors.yellow.950}',
      },
    },
    success: {
      value: {
        base: '{colors.green.50}',
        _dark: '{colors.green.950}',
      },
    },
    info: {
      value: {
        base: '{colors.lightBlue.50}',
        _dark: '{colors.lightBlue.950}',
      },
    },
    // Our additional semantic tokens.
    backdrop: {
      value: {
        base: '{colors.common.white/50}',
        _dark: 'rgba(37, 37, 45, 0.5)',
      },
    },
    body: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.neutral.900}',
      },
    },
    level1: {
      value: {
        base: '{colors.neutral.50}',
        _dark: '{colors.neutral.800}',
      },
    },
    level2: {
      value: {
        base: '{colors.neutral.100}',
        _dark: '{colors.neutral.700}',
      },
    },
    level3: {
      value: {
        base: '{colors.neutral.200}',
        _dark: '{colors.neutral.600}',
      },
    },
    surface: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.common.black}',
      },
    },
    inverse: {
      value: {
        base: '{colors.neutral.800}',
        _dark: '{colors.neutral.100}',
      },
    },
    modal: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.neutral.900}',
      },
    },
  },
  fg: {
    // Newer Chakra V3 semantic tokens.
    DEFAULT: {
      value: {
        _light: '{colors.black}',
        _dark: '{colors.gray.50}',
      },
    },
    muted: {
      value: {
        _light: '{colors.gray.600}',
        _dark: '{colors.gray.400}',
      },
    },
    subtle: {
      value: {
        _light: '{colors.gray.400}',
        _dark: '{colors.gray.500}',
      },
    },
    inverted: {
      value: {
        _light: '{colors.gray.50}',
        _dark: '{colors.black}',
      },
    },
    error: {
      value: {
        _light: '{colors.red.500}',
        _dark: '{colors.red.400}',
      },
    },
    warning: {
      value: {
        _light: '{colors.orange.600}',
        _dark: '{colors.orange.300}',
      },
    },
    success: {
      value: {
        _light: '{colors.green.600}',
        _dark: '{colors.green.300}',
      },
    },
    info: {
      value: {
        _light: '{colors.blue.600}',
        _dark: '{colors.blue.300}',
      },
    },
  },
  // - https://www.chakra-ui.com/docs/theming/colors#semantic-tokens
  //   - border
  border: {
    // Newer Chakra V3 semantic tokens.
    DEFAULT: {
      value: {
        base: '{colors.neutral.200}',
        _dark: '{colors.neutral.800}',
      },
    },
    muted: {
      value: {
        base: '{colors.neutral.100}',
        _dark: '{colors.neutral.900}',
      },
    },
    subtle: {
      value: {
        base: '{colors.neutral.50}',
        _dark: '{colors.neutral.950}',
      },
    },
    emphasized: {
      value: {
        base: '{colors.neutral.300}',
        _dark: '{colors.neutral.700}',
      },
    },
    inverted: {
      value: {
        base: '{colors.neutral.800}',
        _dark: '{colors.neutral.200}',
      },
    },
    error: {
      value: {
        base: '{colors.red.500}',
        _dark: '{colors.red.400}',
      },
    },
    warning: {
      value: {
        base: '{colors.orange.500}',
        _dark: '{colors.orange.400}',
      },
    },
    success: {
      value: {
        base: '{colors.green.500}',
        _dark: '{colors.green.400}',
      },
    },
    info: {
      value: {
        base: '{colors.lightBlue.500}',
        _dark: '{colors.lightBlue.400}',
      },
    },
  },
  // - https://www.chakra-ui.com/docs/theming/colors#semantic-tokens
  //   - text
  text: {
    // Newer Chakra V3 semantic tokens.
    fg: {
      DEFAULT: {
        value: {
          base: '{colors.common.black}',
          _dark: '{colors.neutral.50}',
        },
      },
      muted: {
        value: {
          base: '{colors.neutral.600}',
          _dark: '{colors.neutral.400}',
        },
      },
      subtle: {
        value: {
          base: '{colors.neutral.400}',
          _dark: '{colors.neutral.500}',
        },
      },
      inverted: {
        value: {
          base: '{colors.neutral.50}',
          _dark: '{colors.common.black}',
        },
      },
      error: {
        value: {
          base: '{colors.red.500}',
          _dark: '{colors.red.400}',
        },
      },
      warning: {
        value: {
          base: '{colors.orange.600}',
          _dark: '{colors.orange.300}',
        },
      },
      success: {
        value: {
          base: '{colors.green.600}',
          _dark: '{colors.green.300}',
        },
      },
      info: {
        value: {
          base: '{colors.lightBlue.600}',
          _dark: '{colors.lightBlue.300}',
        },
      },
    },
    // Our additional semantic tokens.
    DEFAULT: {
      value: {
        base: '{colors.neutral.900}',
        _dark: '{colors.common.white}',
      },
    },
    main: {
      value: {
        base: '{colors.neutral.900}',
        _dark: '{colors.common.white}',
      },
    },
    light: {
      value: {
        base: '{colors.neutral.600}',
        _dark: '{colors.neutral.100}',
      },
    },
    lighter: {
      value: {
        base: '{colors.neutral.400}',
        _dark: '{colors.neutral.300}',
      },
    },
    inverse: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.neutral.900}',
      },
    },
    link: {
      value: {
        base: '{colors.purple.500}',
        _dark: '{colors.purple.400}',
      },
    },
  },
  // Our own semantic token of `primary`.
  primary: {
    // Newer Chakra V3 semantic tokens.
    contrast: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.common.black}',
      },
    },
    fg: {
      value: {
        base: '{colors.purple.700}',
        _dark: '{colors.purple.300}',
      },
    },
    subtle: {
      value: {
        base: '{colors.purple.100}',
        _dark: '{colors.purple.900}',
      },
    },
    muted: {
      value: {
        base: '{colors.purple.200}',
        _dark: '{colors.purple.800}',
      },
    },
    emphasized: {
      value: {
        base: '{colors.purple.300}',
        _dark: '{colors.purple.700}',
      },
    },
    solid: {
      value: {
        base: '{colors.purple.600}',
        _dark: '{colors.purple.600}',
      },
    },
    focusRing: {
      value: {
        base: '{colors.purple.600}',
        _dark: '{colors.purple.600}',
      },
    },
    // Our additional semantic tokens.
    text: {
      DEFAULT: {
        value: {
          base: '{colors.purple.600}',
          _dark: '{colors.purple.400}',
        },
      },
      main: {
        value: {
          base: '{colors.purple.600}',
          _dark: '{colors.purple.400}',
        },
      },
      light: {
        value: {
          base: '{colors.purple.400}',
          _dark: '{colors.purple.500}',
        },
      },
      lighter: {
        value: {
          base: '{colors.purple.300}',
          _dark: '{colors.purple.600}',
        },
      },
    },
    bg: {
      DEFAULT: {
        value: {
          base: '{colors.purple.500}',
          _dark: '{colors.purple.400}',
        },
      },
      lighter: {
        value: {
          base: '{colors.purple.50}',
          _dark: '{colors.purple.700}',
        },
      },
      light: {
        value: {
          base: '{colors.purple.200}',
          _dark: '{colors.purple.600}',
        },
      },
      main: {
        value: {
          base: '{colors.purple.500}',
          _dark: '{colors.purple.400}',
        },
      },
      contrast: {
        value: {
          base: '{colors.purple.700}',
          _dark: '{colors.purple.200}',
        },
      },
      contrastMore: {
        value: {
          base: '{colors.purple.900}',
          _dark: '{colors.purple.50}',
        },
      },
      disabled: {
        value: {
          base: '{colors.purple.200}',
          _dark: '{colors.purple.600}',
        },
      },
    },
  },
  // Our own semantic token of `danger`.
  danger: {
    // Newer Chakra V3 semantic tokens.
    contrast: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.common.white}',
      },
    },
    fg: {
      value: {
        base: '{colors.red.700}',
        _dark: '{colors.red.300}',
      },
    },
    subtle: {
      value: {
        base: '{colors.red.100}',
        _dark: '{colors.red.900}',
      },
    },
    muted: {
      value: {
        base: '{colors.red.200}',
        _dark: '{colors.red.800}',
      },
    },
    emphasized: {
      value: {
        base: '{colors.red.300}',
        _dark: '{colors.red.700}',
      },
    },
    solid: {
      value: {
        base: '{colors.red.600}',
        _dark: '{colors.red.600}',
      },
    },
    focusRing: {
      value: {
        base: '{colors.red.600}',
        _dark: '{colors.red.600}',
      },
    },
    // Our additional semantic tokens.
    text: {
      DEFAULT: {
        value: {
          base: '{colors.red.800}',
          _dark: '{colors.red.400}',
        },
      },
      main: {
        value: {
          base: '{colors.red.800}',
          _dark: '{colors.red.400}',
        },
      },
      light: {
        value: {
          base: '{colors.red.600}',
          _dark: '{colors.red.500}',
        },
      },
      lighter: {
        value: {
          base: '{colors.red.400}',
          _dark: '{colors.red.600}',
        },
      },
    },
    bg: {
      DEFAULT: {
        value: {
          base: '{colors.red.500}',
          _dark: '{colors.red.400}',
        },
      },
      lighter: {
        value: {
          base: '{colors.red.100}',
          _dark: '{colors.red.700}',
        },
      },
      light: {
        value: {
          base: '{colors.red.200}',
          _dark: '{colors.red.600}',
        },
      },
      main: {
        value: {
          base: '{colors.red.500}',
          _dark: '{colors.red.400}',
        },
      },
      contrast: {
        value: {
          base: '{colors.red.600}',
          _dark: '{colors.red.200}',
        },
      },
      contrastMore: {
        value: {
          base: '{colors.red.800}',
          _dark: '{colors.red.100}',
        },
      },
      disabled: {
        value: {
          base: '{colors.red.200}',
          _dark: '{colors.red.600}',
        },
      },
    },
  },
  // Our own semantic token of `warning`.
  warning: {
    // Newer Chakra V3 semantic tokens.
    contrast: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.common.white}',
      },
    },
    fg: {
      value: {
        base: '{colors.yellow.700}',
        _dark: '{colors.yellow.300}',
      },
    },
    subtle: {
      value: {
        base: '{colors.yellow.100}',
        _dark: '{colors.yellow.900}',
      },
    },
    muted: {
      value: {
        base: '{colors.yellow.200}',
        _dark: '{colors.yellow.800}',
      },
    },
    emphasized: {
      value: {
        base: '{colors.yellow.300}',
        _dark: '{colors.yellow.700}',
      },
    },
    solid: {
      value: {
        base: '{colors.yellow.600}',
        _dark: '{colors.yellow.600}',
      },
    },
    focusRing: {
      value: {
        base: '{colors.yellow.600}',
        _dark: '{colors.yellow.600}',
      },
    },
    // Our additional semantic tokens.
    text: {
      DEFAULT: {
        value: {
          base: '{colors.yellow.900}',
          _dark: '{colors.yellow.100}',
        },
      },
      main: {
        value: {
          base: '{colors.yellow.900}',
          _dark: '{colors.yellow.100}',
        },
      },
      light: {
        value: {
          base: '{colors.yellow.700}',
          _dark: '{colors.yellow.300}',
        },
      },
      lighter: {
        value: {
          base: '{colors.yellow.600}',
          _dark: '{colors.yellow.500}',
        },
      },
    },
    bg: {
      DEFAULT: {
        value: {
          base: '{colors.yellow.500}',
          _dark: '{colors.yellow.400}',
        },
      },
      lighter: {
        value: {
          base: '{colors.yellow.100}',
          _dark: '{colors.yellow.700}',
        },
      },
      light: {
        value: {
          base: '{colors.yellow.200}',
          _dark: '{colors.yellow.600}',
        },
      },
      main: {
        value: {
          base: '{colors.yellow.500}',
          _dark: '{colors.yellow.400}',
        },
      },
      contrast: {
        value: {
          base: '{colors.yellow.600}',
          _dark: '{colors.yellow.200}',
        },
      },
      contrastMore: {
        value: {
          base: '{colors.yellow.800}',
          _dark: '{colors.yellow.50}',
        },
      },
      disabled: {
        value: {
          base: '{colors.yellow.200}',
          _dark: '{colors.yellow.700}',
        },
      },
    },
  },
  // Our own semantic token of `success`.
  success: {
    // Newer Chakra V3 semantic tokens.
    contrast: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.common.white}',
      },
    },
    fg: {
      value: {
        base: '{colors.green.700}',
        _dark: '{colors.green.300}',
      },
    },
    subtle: {
      value: {
        base: '{colors.green.100}',
        _dark: '{colors.green.900}',
      },
    },
    muted: {
      value: {
        base: '{colors.green.200}',
        _dark: '{colors.green.800}',
      },
    },
    emphasized: {
      value: {
        base: '{colors.green.300}',
        _dark: '{colors.green.700}',
      },
    },
    solid: {
      value: {
        base: '{colors.green.600}',
        _dark: '{colors.green.600}',
      },
    },
    focusRing: {
      value: {
        base: '{colors.green.600}',
        _dark: '{colors.green.600}',
      },
    },
    // Our additional semantic tokens.
    text: {
      DEFAULT: {
        value: {
          base: '{colors.green.800}',
          _dark: '{colors.green.200}',
        },
      },
      main: {
        value: {
          base: '{colors.green.800}',
          _dark: '{colors.green.200}',
        },
      },
      light: {
        value: {
          base: '{colors.green.700}',
          _dark: '{colors.green.400}',
        },
      },
      lighter: {
        value: {
          base: '{colors.green.600}',
          _dark: '{colors.green.600}',
        },
      },
    },
    bg: {
      DEFAULT: {
        value: {
          base: '{colors.green.500}',
          _dark: '{colors.green.400}',
        },
      },
      lighter: {
        value: {
          base: '{colors.green.100}',
          _dark: '{colors.green.800}',
        },
      },
      light: {
        value: {
          base: '{colors.green.200}',
          _dark: '{colors.green.600}',
        },
      },
      main: {
        value: {
          base: '{colors.green.500}',
          _dark: '{colors.green.400}',
        },
      },
      contrast: {
        value: {
          base: '{colors.green.600}',
          _dark: '{colors.green.200}',
        },
      },
      contrastMore: {
        value: {
          base: '{colors.green.700}',
          _dark: '{colors.green.100}',
        },
      },
      disabled: {
        value: {
          base: '{colors.green.300}',
          _dark: '{colors.green.700}',
        },
      },
    },
  },
  // Our own semantic token of `info`.
  info: {
    // Newer Chakra V3 semantic tokens.
    contrast: {
      value: {
        base: '{colors.common.white}',
        _dark: '{colors.common.white}',
      },
    },
    fg: {
      value: {
        base: '{colors.lightBlue.700}',
        _dark: '{colors.lightBlue.300}',
      },
    },
    subtle: {
      value: {
        base: '{colors.lightBlue.100}',
        _dark: '{colors.lightBlue.900}',
      },
    },
    muted: {
      value: {
        base: '{colors.lightBlue.200}',
        _dark: '{colors.lightBlue.800}',
      },
    },
    emphasized: {
      value: {
        base: '{colors.lightBlue.300}',
        _dark: '{colors.lightBlue.700}',
      },
    },
    solid: {
      value: {
        base: '{colors.lightBlue.600}',
        _dark: '{colors.lightBlue.600}',
      },
    },
    focusRing: {
      value: {
        base: '{colors.lightBlue.600}',
        _dark: '{colors.lightBlue.600}',
      },
    },
    // Our additional semantic tokens.
    text: {
      DEFAULT: {
        value: {
          base: '{colors.lightBlue.700}',
          _dark: '{colors.lightBlue.400}',
        },
      },
      main: {
        value: {
          base: '{colors.lightBlue.700}',
          _dark: '{colors.lightBlue.400}',
        },
      },
      light: {
        value: {
          base: '{colors.lightBlue.600}',
          _dark: '{colors.lightBlue.500}',
        },
      },
      lighter: {
        value: {
          base: '{colors.lightBlue.400}',
          _dark: '{colors.lightBlue.600}',
        },
      },
    },
    bg: {
      DEFAULT: {
        value: {
          base: '{colors.lightBlue.500}',
          _dark: '{colors.lightBlue.400}',
        },
      },
      lighter: {
        value: {
          base: '{colors.lightBlue.100}',
          _dark: '{colors.lightBlue.800}',
        },
      },
      light: {
        value: {
          base: '{colors.lightBlue.200}',
          _dark: '{colors.lightBlue.600}',
        },
      },
      main: {
        value: {
          base: '{colors.lightBlue.500}',
          _dark: '{colors.lightBlue.400}',
        },
      },
      contrast: {
        value: {
          base: '{colors.lightBlue.600}',
          _dark: '{colors.lightBlue.200}',
        },
      },
      contrastMore: {
        value: {
          base: '{colors.lightBlue.800}',
          _dark: '{colors.lightBlue.100}',
        },
      },
      disabled: {
        value: {
          base: '{colors.lightBlue.300}',
          _dark: '{colors.lightBlue.600}',
        },
      },
    },
  },
  blue: {
    contrast: {
      value: {
        _light: 'white',
        _dark: 'white',
      },
    },
    fg: {
      value: {
        _light: '{colors.blue.700}',
        _dark: '{colors.blue.300}',
      },
    },
    subtle: {
      value: {
        _light: '{colors.blue.100}',
        _dark: '{colors.blue.900}',
      },
    },
    muted: {
      value: {
        _light: '{colors.blue.200}',
        _dark: '{colors.blue.800}',
      },
    },
    emphasized: {
      value: {
        _light: '{colors.blue.300}',
        _dark: '{colors.blue.700}',
      },
    },
    solid: {
      value: {
        _light: '{colors.blue.600}',
        _dark: '{colors.blue.600}',
      },
    },
    focusRing: {
      value: {
        _light: '{colors.blue.600}',
        _dark: '{colors.blue.600}',
      },
    },
  },
});
