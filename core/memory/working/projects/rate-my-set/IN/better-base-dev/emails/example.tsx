import * as React from 'react';

import { Body, Container, Head, Html, Preview, Text } from '@react-email/components';

import FooterTransactional from './components/FooterTransactional';
import LogoSmall from './components/LogoSmall';
import { Var } from './core/variables';

interface ExampleProps {
  oneVariable?: string;
  anotherVariable?: string;
}

export const Example = ({
  oneVariable = Var('one_variable', 'One Variable'),
  anotherVariable = Var('another_variable', 'Another Variable'),
}: ExampleProps) => (
  <Html>
    <Head />
    <Preview>Example Email Preview</Preview>
    <Body style={main}>
      <Container style={container}>
        <LogoSmall style={{ marginTop: 32, marginBottom: 32 }} />
        <Text style={paragraph}>Here is an example email.</Text>
        <Text style={paragraph}>Here is {oneVariable}.</Text>
        <Text style={paragraph}>Here is {anotherVariable}.</Text>
        <FooterTransactional />
      </Container>
    </Body>
  </Html>
);

export default Example;

const main = {
  backgroundColor: '#ffffff',
  fontFamily:
    '"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen-Sans,Ubuntu,Cantarell,"Helvetica Neue",sans-serif',
};

const container = {
  margin: '0 auto',
  padding: '20px 0 48px',
  width: '600px',
};

const paragraph = {
  margin: '0 0 16px',
  fontSize: '16px',
  fontStyle: 'normal',
  fontWeight: '400',
  lineHeight: '133%',
  color: '#000000',
};
