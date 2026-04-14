import * as React from 'react';

import { Hr, Link, Text } from '@react-email/components';

import { SUPPORT_EMAIL, WEB_APP_ROOT_URL } from '../core/variables';

interface Props {
  webAppRootUrl?: string;
  supportEmail?: string;
}

const FooterTransactional = ({
  webAppRootUrl = WEB_APP_ROOT_URL,
  supportEmail = SUPPORT_EMAIL,
}: Props) => (
  <>
    <Hr style={hr} />
    <Text style={footerText}>
      <Link href={webAppRootUrl}>Better Base</Link>
    </Text>
    <Text style={footerText}>
      If you are not sure why you’re receiving this, please contact us at{' '}
      <Link href={`mailto:${supportEmail}`}>{supportEmail}</Link>
    </Text>
  </>
);

export default FooterTransactional;

const hr = {
  borderColor: '#F1F1F1',
  margin: '42px 0 26px',
};

const footerText = {
  fontSize: '10px',
  fontStyle: 'normal',
  fontWeight: '400',
  lineHeight: '133%',
  color: '#000000',
};
