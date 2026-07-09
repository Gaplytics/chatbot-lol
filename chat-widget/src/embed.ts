import React from 'react';
import { createRoot } from 'react-dom/client';
import { Widget } from './Widget';
import './styles/widget.css';

function mountWidget() {
  const scriptTags = document.getElementsByTagName('script');
  // Find our specific script tag
  let scriptTag = null;
  for (let i = 0; i < scriptTags.length; i++) {
    if (scriptTags[i].src.includes('embed')) {
      scriptTag = scriptTags[i];
      break;
    }
  }

  const tokenUrl = scriptTag?.getAttribute('data-token-url') || 'http://localhost:8080/token';
  const botName = scriptTag?.getAttribute('data-bot-name') || 'Gaply';
  const theme = scriptTag?.getAttribute('data-theme') || 'light';
  const tenantId = scriptTag?.getAttribute('data-tenant-id') || 'institutes';

  // Create host element
  const host = document.createElement('div');
  host.id = 'gaply-widget-root';
  document.body.appendChild(host);

  // Render React App
  const root = createRoot(host);
  root.render(React.createElement(Widget, { tokenUrl, botName, theme, tenantId }));
}

// Automatically mount when script loads
if (document.readyState === 'complete') {
  mountWidget();
} else {
  window.addEventListener('load', mountWidget);
}
