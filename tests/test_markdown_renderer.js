/**
 * Automated test suite for Markdown integration in Agent Manager
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log('🧪 Starting Markdown integration test suite...');

// 1. Verify all expected static files exist and have non-zero size
const requiredFiles = [
  'agent_manager/static/vendor/marked.min.js',
  'agent_manager/static/vendor/purify.min.js',
  'agent_manager/static/markdown-renderer.js',
  'agent_manager/static/markdown.css'
];

for (const relPath of requiredFiles) {
  const fullPath = path.resolve(__dirname, '..', relPath);
  assert(fs.existsSync(fullPath), `Missing file: ${relPath}`);
  const stats = fs.statSync(fullPath);
  assert(stats.size > 100, `File ${relPath} is unexpectedly small (${stats.size} bytes)`);
  console.log(`  ✓ File verified: ${relPath} (${stats.size} bytes)`);
}

// 2. Verify index.html includes the required stylesheets and scripts
const indexPath = path.resolve(__dirname, '../agent_manager/static/index.html');
const indexHtml = fs.readFileSync(indexPath, 'utf8');

assert(indexHtml.includes('/static/markdown.css'), 'index.html must include /static/markdown.css');
assert(indexHtml.includes('/static/vendor/marked.min.js'), 'index.html must include marked.min.js');
assert(indexHtml.includes('/static/vendor/purify.min.js'), 'index.html must include purify.min.js');
assert(indexHtml.includes('/static/markdown-renderer.js'), 'index.html must include markdown-renderer.js');
console.log('  ✓ index.html references all markdown assets correctly');

// 3. Verify marked parser with custom code and table renderers
const marked = require(path.resolve(__dirname, '../agent_manager/static/vendor/marked.min.js'));

// Create a simulated window environment
const mockWindow = {
  marked: marked,
  document: {
    addEventListener: () => {},
    readyState: 'complete'
  }
};

const rendererCode = fs.readFileSync(path.resolve(__dirname, '../agent_manager/static/markdown-renderer.js'), 'utf8');
const fn = new Function('window', 'document', rendererCode);
fn(mockWindow, mockWindow.document);

assert(typeof mockWindow.renderMarkdown === 'function', 'renderMarkdown must be defined on window');

// Test headings
const headingRes = mockWindow.renderMarkdown('# Title 1\n## Title 2\n### Title 3');
assert(headingRes.includes('<h1>Title 1</h1>'), 'Heading 1 should render');
assert(headingRes.includes('<h2>Title 2</h2>'), 'Heading 2 should render');
assert(headingRes.includes('<h3>Title 3</h3>'), 'Heading 3 should render');
console.log('  ✓ Headings rendered properly');

// Test bold, italic, strikethrough
const formattingRes = mockWindow.renderMarkdown('**bold text** and *italic text* and ~~deleted~~');
assert(formattingRes.includes('<strong>bold text</strong>'), 'Bold should render');
assert(formattingRes.includes('<em>italic text</em>'), 'Italic should render');
assert(formattingRes.includes('<del>deleted</del>'), 'Strikethrough should render');
console.log('  ✓ Text formatting (bold, italic, strikethrough) rendered properly');

// Test code block wrapping with language badge and copy button
const codeSnippet = '```python\ndef hello():\n    return "world"\n```';
const codeRes = mockWindow.renderMarkdown(codeSnippet);
assert(codeRes.includes('code-block-wrapper'), 'Code block should have code-block-wrapper');
assert(codeRes.includes('code-header'), 'Code block should have code-header');
assert(codeRes.includes('code-lang'), 'Code block should display code language');
assert(codeRes.includes('PYTHON'), 'Code language should be PYTHON');
assert(codeRes.includes('btn-copy-code'), 'Code block should have a copy button');
assert(codeRes.includes('language-python'), 'Code element should have language-python class');
assert(codeRes.includes('def hello():'), 'Code body should be present');
console.log('  ✓ Code block with copy button and language tag rendered properly');

// Test markdown table rendering
const tableSnippet = '| Header A | Header B |\n| --- | --- |\n| Cell 1 | Cell 2 |';
const tableRes = mockWindow.renderMarkdown(tableSnippet);
assert(tableRes.includes('markdown-table-wrapper'), 'Table should be wrapped in markdown-table-wrapper');
assert(tableRes.includes('<table>'), 'Table tag should be present');
assert(tableRes.includes('Header A'), 'Header cell should be present');
assert(tableRes.includes('Cell 1'), 'Body cell should be present');
console.log('  ✓ Tables rendered properly');

// Test links with safe attributes
const linkSnippet = '[Antigravity Docs](https://gemini.google.com/antigravity)';
const linkRes = mockWindow.renderMarkdown(linkSnippet);
assert(linkRes.includes('href="https://gemini.google.com/antigravity"'), 'Link href should match');
assert(linkRes.includes('target="_blank"'), 'Link should have target="_blank"');
assert(linkRes.includes('rel="noopener noreferrer"'), 'Link should have rel="noopener noreferrer"');
console.log('  ✓ Markdown links rendered with security attributes');

// Test fallback parser when marked is undefined
const fallbackWindow = {
  document: {
    addEventListener: () => {},
    readyState: 'complete'
  }
};
fn(fallbackWindow, fallbackWindow.document);
const fallbackRes = fallbackWindow.renderMarkdown('**bold** and `code`\n```js\nconsole.log(1);\n```');
assert(fallbackRes.includes('<strong>bold</strong>'), 'Fallback bold should render');
assert(fallbackRes.includes('<code>code</code>'), 'Fallback inline code should render');
assert(fallbackRes.includes('code-block-wrapper'), 'Fallback code fence should render wrapper');
console.log('  ✓ Fallback parser works when marked library is absent');

console.log('🎉 All JavaScript/Markdown tests passed successfully!\n');
