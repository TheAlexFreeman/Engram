import * as Sentry from '@sentry/react';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/sentry-test')({
  component: SentryTest,
});

function SentryTest() {
  const handleTestError = () => {
    throw new Error('Test error from /sentry-test route');
  };

  const handleCaptureException = () => {
    try {
      throw new Error('Captured exception from /sentry-test route');
    } catch (e) {
      Sentry.captureException(e);
      alert('Exception captured and sent to Sentry');
    }
  };

  const handleCaptureMessage = () => {
    Sentry.captureMessage('Test message from /sentry-test route', 'info');
    alert('Message sent to Sentry');
  };

  const envVars = {
    VITE_ENVIRONMENT: import.meta.env.VITE_ENVIRONMENT,
    VITE_SENTRY_IS_ENABLED: import.meta.env.VITE_SENTRY_IS_ENABLED,
    VITE_SENTRY_ORG: import.meta.env.VITE_SENTRY_ORG,
    VITE_SENTRY_PROJECT: import.meta.env.VITE_SENTRY_PROJECT,
    VITE_SENTRY_RELEASE: import.meta.env.VITE_SENTRY_RELEASE,
    PROD: import.meta.env.PROD,
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'monospace' }}>
      <h1>Sentry Test Page</h1>

      <section style={{ marginBottom: '2rem' }}>
        <h2>Environment Variables</h2>
        <pre
          style={{
            background: '#f4f4f4',
            padding: '1rem',
            borderRadius: '4px',
            overflow: 'auto',
          }}
        >
          {JSON.stringify(envVars, null, 2)}
        </pre>
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2>Test Actions</h2>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <button
            onClick={handleTestError}
            style={{
              padding: '0.75rem 1.5rem',
              background: '#dc2626',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Throw Uncaught Error
          </button>

          <button
            onClick={handleCaptureException}
            style={{
              padding: '0.75rem 1.5rem',
              background: '#ea580c',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Capture Exception
          </button>

          <button
            onClick={handleCaptureMessage}
            style={{
              padding: '0.75rem 1.5rem',
              background: '#2563eb',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Send Test Message
          </button>
        </div>
      </section>

      <section>
        <h2>Instructions</h2>
        <ul>
          <li>
            <strong>Throw Uncaught Error:</strong> Throws an error that will crash the component and
            be caught by Sentry&apos;s error boundary
          </li>
          <li>
            <strong>Capture Exception:</strong> Catches an error and manually sends it to Sentry
          </li>
          <li>
            <strong>Send Test Message:</strong> Sends an info-level message to Sentry
          </li>
        </ul>
        <p style={{ marginTop: '1rem', color: '#666' }}>
          After triggering an error, check your Sentry dashboard to verify the error appears with
          proper source maps (you should see original TypeScript/JSX code in stack traces).
        </p>
      </section>
    </div>
  );
}
