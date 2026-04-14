import * as React from 'react';

import { Body, Button, Container, Head, Html, Preview, Text } from '@react-email/components';

import FooterTransactional from './components/FooterTransactional';
import LogoSmall from './components/LogoSmall';
import { Var, WEB_APP_ROOT_URL } from './core/variables';
import { button, container, main, paragraph } from './emailStyles';

interface TeamInvitationProps {
  teamDisplayName?: string;
  actionText?: string;
  secretLink?: string;
}

export const TeamInvitation = ({
  teamDisplayName = Var('team_display_name', 'Team Display Name'),
  actionText = Var('action_text', 'Accept Invitation'),
  secretLink = Var('secret_link', WEB_APP_ROOT_URL),
}: TeamInvitationProps) => (
  <Html>
    <Head />
    <Preview>You have been invited to join {teamDisplayName}.</Preview>
    <Body style={main}>
      <Container style={container}>
        <LogoSmall style={{ marginTop: 32, marginBottom: 32 }} />
        <Text style={paragraph}>
          You have been invited to join {teamDisplayName}. If you do not wish to join this account,
          you may ignore this email.
        </Text>
        <Button href={secretLink} style={{ ...button }}>
          {actionText}
        </Button>
        <FooterTransactional />
      </Container>
    </Body>
  </Html>
);

export default TeamInvitation;
