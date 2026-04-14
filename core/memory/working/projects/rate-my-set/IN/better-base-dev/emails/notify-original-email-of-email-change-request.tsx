import * as React from 'react';

import { Body, Container, Head, Html, Link, Preview, Text } from '@react-email/components';

import FooterTransactional from './components/FooterTransactional';
import LogoSmall from './components/LogoSmall';
import { SUPPORT_EMAIL, Var } from './core/variables';
import { container, main, paragraph, textLink } from './emailStyles';

interface NotifyOriginalEmailOfEmailChangeRequestProps {
  fromEmail?: string;
  toEmail?: string;
  supportEmail?: string;
}

export const NotifyOriginalEmailOfEmailChangeRequest = ({
  fromEmail = Var('from_email', 'from_email@example.com'),
  toEmail = Var('to_email', 'to_email@example.com'),
  supportEmail = Var('support_email', SUPPORT_EMAIL),
}: NotifyOriginalEmailOfEmailChangeRequestProps) => (
  <Html>
    <Head />
    <Preview>Email Change Request Made</Preview>
    <Body style={main}>
      <Container style={container}>
        <LogoSmall style={{ marginTop: 32, marginBottom: 32 }} />
        <Text style={paragraph}>
          There has been a request to change your email from {fromEmail} to {toEmail}. If this was
          not initiated by you, please{' '}
          <Link href={`mailto:${supportEmail}`} style={textLink}>
            contact support
          </Link>{' '}
          immediately.
        </Text>
        <FooterTransactional />
      </Container>
    </Body>
  </Html>
);

export default NotifyOriginalEmailOfEmailChangeRequest;
