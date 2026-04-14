import * as React from 'react';

import { Img } from '@react-email/components';

import { Static } from '../core/variables';

const LOGO_SMALL_SRC = Static('logos/email-logo-small.png');
const LOGO_SMALL_WIDTH = 41;
const LOGO_SMALL_HEIGHT = 32;
const LOGO_SMALL_BORDER_RADIUS = 0;

interface Props {
  style?: React.CSSProperties;
}

const LogoSmall = ({ style: providedStyles }: Props) => (
  <Img
    src={LOGO_SMALL_SRC}
    width={LOGO_SMALL_WIDTH.toString()}
    height={LOGO_SMALL_HEIGHT.toString()}
    alt="Better Base"
    style={{ ...baseStyles, ...(providedStyles || {}) }}
  />
);

export default LogoSmall;

const baseStyles = {
  borderRadius: LOGO_SMALL_BORDER_RADIUS,
  width: LOGO_SMALL_WIDTH,
  height: LOGO_SMALL_HEIGHT,
};
