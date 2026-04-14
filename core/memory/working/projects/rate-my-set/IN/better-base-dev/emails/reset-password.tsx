import * as React from 'react';

import { Body, Container, Head, Html, Link, Preview, Text } from '@react-email/components';

import FooterTransactional from './components/FooterTransactional';
import LogoSmall from './components/LogoSmall';
import { Var, WEB_APP_ROOT_URL } from './core/variables';
import { container, highlighted, main, paragraph } from './emailStyles';

interface ResetPasswordProps {
  secretLink?: string;
}

export const ResetPassword = ({
  secretLink = Var('secret_link', WEB_APP_ROOT_URL),
}: ResetPasswordProps) => (
  <Html>
    <Head />
    <Preview>Reset Your Password for Better Base</Preview>
    <Body style={main}>
      <Container style={container}>
        <LogoSmall style={{ marginTop: 32, marginBottom: 32 }} />
        <Text style={paragraph}>
          We have received a request to reset your password. If this was not from you, you can
          safely disregard this email.
        </Text>
        <Text style={paragraph}>Please go to the following page and choose a new password:</Text>
        <Link href={secretLink} style={highlighted}>
          Reset Your Password
        </Link>
        <FooterTransactional />
      </Container>
    </Body>
  </Html>
);

export default ResetPassword;
