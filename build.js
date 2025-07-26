// build.js
// This script pre-builds your site to be static and SEO-friendly.

import fetch from 'node-fetch';
import fs from 'fs';
import { marked } from 'marked';

// --- Configuration ---
// Uses the GITHUB_CONFIG from your config.js file
import { GITHUB_CONFIG } from './config.js';
const SITE_URL = 'https://www.zerodaybrief.com'; // Your correct domain
const POSTS_DIR = '_posts';
const OUTPUT_DIR = 'dist'; // We'll put the final site here
const POSTS_OUTPUT_DIR = `${OUTPUT_DIR}/posts`;

// --- Helper Functions ---

// Function to fetch all post filenames from GitHub
async function getPostFiles() {
    const url = `https://api.github.com/repos/${GITHUB_CONFIG.OWNER}/${GITHUB_CONFIG.REPO}/contents/${POSTS_DIR}`;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`GitHub API error: ${response.statusText}`);
        const files = await response.json();
        return files.filter(file => file.name.endsWith('.md'));
    } catch (error) {
        console.error('Error fetching post list from GitHub:', error);
        return [];
    }
}

// Function to parse front matter and markdown content
function parseMarkdown(markdown) {
    const frontMatterMatch = markdown.match(/---([\s\S]*?)---/);
    const frontMatterText = frontMatterMatch ? frontMatterMatch[1] : '';
    const content = markdown.replace(/---[\s\S]*?---/, '').trim();

    const postData = {};
    frontMatterText.split('\n').forEach(line => {
        const parts = line.split(':');
        if (parts.length > 1) {
            const key = parts[0].trim();
            const value = parts.slice(1).join(':').trim().replace(/^"(.*)"$/, '$1');
            postData[key] = value;
        }
    });

    postData.content = marked.parse(content);
    return postData;
}

// --- Main Build Logic ---

async function buildSite() {
    console.log('Starting build process...');

    // 1. Clean and create output directories
    if (fs.existsSync(OUTPUT_DIR)) {
        fs.rmSync(OUTPUT_DIR, { recursive: true, force: true });
    }
    fs.mkdirSync(OUTPUT_DIR);
    fs.mkdirSync(POSTS_OUTPUT_DIR);
    console.log('Output directory cleaned.');

    // 2. Fetch all posts
    const postFiles = await getPostFiles();
    if (!postFiles.length) {
        console.log('No posts found. Exiting.');
        return;
    }

    const allPosts = (await Promise.all(postFiles.map(async file => {
        const postResponse = await fetch(file.download_url);
        const markdown = await postResponse.text();
        const postData = parseMarkdown(markdown);
        postData.slug = file.name.replace('.md', '');
        postData.url = `${SITE_URL}/posts/${postData.slug}.html`;
        return postData;
    }))).sort((a, b) => new Date(b.date) - new Date(a.date));

    console.log(`Fetched ${allPosts.length} posts.`);

    // 3. Generate individual post pages
    const postTemplate = fs.readFileSync('post.html', 'utf-8');
    allPosts.forEach(post => {
        let postHtml = postTemplate
            .replace(/{{POST_TITLE}}/g, post.title)
            .replace(/{{POST_DATE}}/g, new Date(post.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }))
            .replace(/{{POST_CONTENT}}/g, post.content)
            .replace(/{{CANONICAL_URL}}/g, post.url); // Set canonical URL for the post

        fs.writeFileSync(`${POSTS_OUTPUT_DIR}/${post.slug}.html`, postHtml);
    });
    console.log('Generated individual post pages.');

    // 4. Generate the index.html page
    const indexTemplate = fs.readFileSync('index.html', 'utf-8');
    const postCardsHtml = allPosts.map(post => {
        const categoryColors = {
            'zero-day': 'bg-red-500/20 text-red-300 border-red-500/30',
            'hot-attacks': 'bg-orange-500/20 text-orange-300 border-orange-500/30',
            'tools': 'bg-sky-500/20 text-sky-300 border-sky-500/30',
            'tricks': 'bg-green-500/20 text-green-300 border-green-500/30'
        };
        const colorClasses = categoryColors[post.category] || 'bg-gray-500/20 text-gray-300';
        // The `data-category` attribute is added for client-side filtering
        return `
        <div class="scroll-animate bg-black bg-opacity-30 p-6 rounded-xl border border-gray-800 hover:border-fuchsia-500 transition-all duration-300 flex flex-col" data-category="${post.category}" data-title="${post.title}" data-excerpt="${post.excerpt}">
            <div>
                <div class="flex justify-between items-center mb-3">
                    <p class="font-mono text-sm text-gray-500">${new Date(post.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
                    <span class="font-mono text-xs py-1 px-2 rounded-full ${colorClasses}">${post.category.replace('-', ' ')}</span>
                </div>
                <h3 class="text-2xl font-bold text-white mb-4">${post.title}</h3>
                <p class="text-gray-400 flex-grow">${post.excerpt}</p>
            </div>
            <a href="posts/${post.slug}.html" class="read-more-btn mt-6 text-fuchsia-400 font-bold self-start hover:text-fuchsia-300">Read More →</a>
        </div>`;
    }).join('');

    // Replace the placeholder in index.html with the generated cards
    const finalIndexHtml = indexTemplate.replace('', postCardsHtml);
    fs.writeFileSync(`${OUTPUT_DIR}/index.html`, finalIndexHtml);
    console.log('Generated index.html page.');

    // 5. Generate sitemap.xml
    const sitemapUrls = allPosts.map(post => `
  <url>
    <loc>${post.url}</loc>
    <lastmod>${new Date(post.date).toISOString().split('T')[0]}</lastmod>
    <priority>0.8</priority>
  </url>`).join('');

    const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${SITE_URL}/</loc>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>${SITE_URL}/about.html</loc>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>${SITE_URL}/services.html</loc>
    <priority>0.7</priority>
  </url>${sitemapUrls}
</urlset>`;
    fs.writeFileSync(`${OUTPUT_DIR}/sitemap.xml`, sitemap);
    console.log('Generated sitemap.xml.');

    // 6. Copy over static files (CSS, images, other HTML pages)
    const staticFilesToCopy = ['about.html', 'services.html', 'config.js', 'robots.txt', 'CNAME'];
    staticFilesToCopy.forEach(file => {
        if (fs.existsSync(file)) {
            fs.copyFileSync(file, `${OUTPUT_DIR}/${file}`);
        }
    });
    console.log('Copied static files.');
    
    console.log('\nBuild complete! Your static site is ready in the "dist" directory.');
}

buildSite();