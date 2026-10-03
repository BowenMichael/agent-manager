#!/usr/bin/env node
/**
 * One-Click Setup Script for Agent-Driven Development Repositories
 * Usage: node setup.js <owner/repo> <github-token>
 */

const https = require('https');

const [,, targetRepo, token] = process.argv;

if (!targetRepo || !token) {
  console.log('Usage: node setup.js <owner/repo> <github-token>');
  console.log('Example: node setup.js myorg/my-new-app ghp_xxxxxxxxxxxx');
  process.exit(1);
}

const [owner, repo] = targetRepo.split('/');

function request(path, method, payload) {
  return new Promise((resolve, reject) => {
    const data = payload ? JSON.stringify(payload) : null;
    const req = https.request({
      hostname: 'api.github.com',
      path,
      method,
      headers: {
        'User-Agent': 'Agent-Template-Setup',
        'Authorization': `token ${token}`,
        'Content-Type': 'application/json',
        ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {})
      }
    }, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve({ status: res.statusCode, data: body ? JSON.parse(body) : null }));
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

const labels = [
  { name: 'agent:ready', color: '0e8a16', description: 'Queued for autonomous agent pick-up' },
  { name: 'agent:in-progress', color: 'fbca04', description: 'Agent actively implementing & testing' },
  { name: 'agent:needs-approval', color: 'd93f0b', description: 'Paused: High token usage or scope clarification needed' },
  { name: 'agent:review', color: '6f42c1', description: 'PR opened with video demo & screenshots' }
];

async function main() {
  console.log(`🚀 Initializing Agent-Driven Workflow for ${owner}/${repo}...`);

  // 1. Create Labels
  console.log('🏷️ Setting up GitHub workflow labels...');
  for (const label of labels) {
    const res = await request(`/repos/${owner}/${repo}/labels`, 'POST', label);
    if (res.status === 201) {
      console.log(`   ✅ Created label: ${label.name}`);
    } else if (res.status === 422) {
      console.log(`   ℹ️ Label already exists: ${label.name}`);
    } else {
      console.log(`   ⚠️ Label ${label.name}: ${res.status}`);
    }
  }

  console.log('\n🎉 Repository setup complete!');
  console.log('Next steps:');
  console.log('1. Copy mcp_config.template.json to your global ~/.gemini/config/mcp_config.json');
  console.log('2. Add your GitHub token to mcp_config.json');
  console.log('3. In Antigravity, schedule your recurring daemon poller:');
  console.log('   /schedule CronExpression="*/3 * * * *" Prompt="Check repository ' + owner + '/' + repo + ' for agent:ready issues..."');
}

main().catch(err => {
  console.error('❌ Error initializing repository:', err);
  process.exit(1);
});
