import * as React from 'react';

import { Body, Container, Head, Html, Link, Preview, Text } from '@react-email/components';

import FooterTransactional from './components/FooterTransactional';
import LogoSmall from './components/LogoSmall';
import { Var, WEB_APP_ROOT_URL } from './core/variables';
import { container, highlighted, main, paragraph } from './emailStyles';

interface VerifyEmailProps {
  secretLink?: string;
}

export const VerifyEmail = ({
  secretLink = Var('secret_link', WEB_APP_ROOT_URL),
}: VerifyEmailProps) => (
  <Html>
    <Head />
    <Preview>Verify Your Email</Preview>
    <Body style={main}>
      <Container style={container}>
        <LogoSmall style={{ marginTop: 32, marginBottom: 32 }} />
        <Text style={paragraph}>Please verify this email by clicking the link below: </Text>
        <Link href={secretLink} style={highlighted}>
          Verify Your Email
        </Link>
        <FooterTransactional />
      </Container>
    </Body>
  </Html>
);

export default VerifyEmail;
