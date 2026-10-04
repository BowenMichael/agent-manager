/**
 * Modular Markdown Renderer for Agent Manager
 * Renders agent responses, thought traces, and CLI outputs as formatted HTML.
 * Includes GFM support, code block wrapping, copy-to-clipboard, and XSS sanitization.
 */

(function (window) {
  'use strict';

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function setupMarkedRenderer() {
    if (!window.marked || typeof window.marked.use !== 'function') {
      return;
    }

    const renderer = {
      code(token) {
        // Handles both object parameter (marked v4+) and positional arguments (marked v2-v3)
        const codeText = (typeof token === 'object' && token !== null) ? token.text : String(token || '');
        const lang = ((typeof token === 'object' && token !== null) ? token.lang : arguments[1]) || '';
        const cleanLang = (lang || '').split(/\s+/)[0] || '';
        const escapedCode = escapeHtml(codeText);
        const displayLang = cleanLang ? escapeHtml(cleanLang.toUpperCase()) : 'TEXT';

        return [
          '<div class="code-block-wrapper">',
          '  <div class="code-header">',
          `    <span class="code-lang">${displayLang}</span>`,
          '    <button class="btn-copy-code" type="button" title="Copy code snippet">',
          '      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
          '      <span>Copy</span>',
          '    </button>',
          '  </div>',
          `  <pre><code class="language-${escapeHtml(cleanLang)}">${escapedCode}</code></pre>`,
          '</div>'
        ].join('\n');
      },
      link(token) {
        const href = (typeof token === 'object' && token !== null) ? token.href : String(token || '');
        const title = (typeof token === 'object' && token !== null) ? token.title : arguments[1];
        const text = (typeof token === 'object' && token !== null) ? token.text : arguments[2];
        const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
        const safeHref = escapeHtml(href);
        return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer"${titleAttr}>${text}</a>`;
      }
    };

    window.marked.use({
      breaks: true,
      gfm: true,
      renderer: renderer
    });
  }

  function fallbackParse(str) {
    if (!str) return '';
    let out = escapeHtml(str);

    // Code blocks
    out = out.replace(/```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```/g, function (_, lang, code) {
      const cleanLang = lang.trim() || 'TEXT';
      return [
        '<div class="code-block-wrapper">',
        '  <div class="code-header">',
        `    <span class="code-lang">${cleanLang}</span>`,
        '    <button class="btn-copy-code" type="button">Copy</button>',
        '  </div>',
        `  <pre><code>${code}</code></pre>`,
        '</div>'
      ].join('\n');
    });

    // Inline code
    out = out.replace(/`([^`\n]+)`/g, '<code>$1</code>');

    // Bold & italic
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Links: [text](url)
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Newlines
    out = out.replace(/\n/g, '<br>');

    return out;
  }

  function renderMarkdown(content) {
    if (!content) return '';
    const raw = String(content);

    let html = '';
    if (window.marked && typeof window.marked.parse === 'function') {
      try {
        html = window.marked.parse(raw);
      } catch (err) {
        console.warn('[MarkdownRenderer] marked.parse failed, falling back:', err);
        html = fallbackParse(raw);
      }
    } else {
      html = fallbackParse(raw);
    }

    // Wrap tables for responsive horizontal scrolling
    if (html.includes('<table')) {
      html = html.replace(/<table(\s[^>]*>|>)/g, '<div class="markdown-table-wrapper"><table$1').replace(/<\/table>/g, '</table></div>');
    }

    // Sanitize with DOMPurify if available
    if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
      html = window.DOMPurify.sanitize(html, {
        ADD_TAGS: ['button', 'input', 'svg', 'path', 'rect', 'polyline', 'line'],
        ADD_ATTR: ['target', 'rel', 'class', 'type', 'checked', 'disabled', 'width', 'height', 'viewBox', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'd', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'points']
      });
    }

    return `<div class="markdown-body">${html}</div>`;
  }

  // Setup click event delegation for copy code buttons
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('.btn-copy-code');
    if (!btn) return;

    const wrapper = btn.closest('.code-block-wrapper');
    if (!wrapper) return;

    const codeEl = wrapper.querySelector('pre code');
    if (!codeEl) return;

    const textToCopy = codeEl.innerText || codeEl.textContent || '';
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      const textarea = document.createElement('textarea');
      textarea.value = textToCopy;
      document.body.appendChild(textarea);
      textarea.select();
      try { document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(textarea);
      markCopied(btn);
      return;
    }

    navigator.clipboard.writeText(textToCopy).then(function () {
      markCopied(btn);
    }).catch(function (err) {
      console.error('[MarkdownRenderer] Failed to copy text:', err);
    });
  });

  function markCopied(btn) {
    const originalHtml = btn.innerHTML;
    btn.classList.add('copied');
    btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Copied!</span>';
    setTimeout(function () {
      btn.classList.remove('copied');
      btn.innerHTML = originalHtml;
    }, 2000);
  }

  // Initialize
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupMarkedRenderer);
  } else {
    setupMarkedRenderer();
  }

  // Export functions to global window
  window.renderMarkdown = renderMarkdown;
  window.setupMarkedRenderer = setupMarkedRenderer;

})(typeof window !== 'undefined' ? window : this);
