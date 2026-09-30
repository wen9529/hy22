import express, { Request, Response } from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: '10mb' }));

// API: Proxy fetch single URL
app.post('/api/fetch-url', async (req: Request, res: Response) => {
  const { url } = req.body;
  if (!url || typeof url !== 'string') {
    return res.status(400).json({ success: false, error: 'URL is required' });
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
      },
    });
    clearTimeout(timeout);

    if (!response.ok) {
      return res.status(response.status).json({
        success: false,
        error: `HTTP ${response.status} ${response.statusText}`,
      });
    }

    const contentType = response.headers.get('content-type') || '';
    const text = await response.text();

    let json = null;
    try {
      json = JSON.parse(text);
    } catch {
      // not json, keep text
    }

    return res.json({
      success: true,
      data: json || text,
      isJson: json !== null,
      rawText: text,
      status: response.status,
    });
  } catch (err: any) {
    return res.status(500).json({
      success: false,
      error: err.name === 'AbortError' ? '请求超时 (Timeout after 8s)' : (err.message || 'Fetch failed'),
    });
  }
});

// API: Batch fetch with mirror fallbacks
app.post('/api/batch-fetch', async (req: Request, res: Response) => {
  const { items } = req.body; // array of { id, name, primaryUrl, fallbackUrl }
  if (!Array.isArray(items)) {
    return res.status(400).json({ success: false, error: 'Items must be an array' });
  }

  const results = await Promise.allSettled(
    items.map(async (item: any) => {
      const urlsToTry = [item.primaryUrl, item.fallbackUrl].filter(Boolean);
      let lastError = '';

      for (const targetUrl of urlsToTry) {
        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 6000);

          const resp = await fetch(targetUrl, {
            signal: controller.signal,
            headers: {
              'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
              'Accept': 'application/json, text/plain, */*',
            },
          });
          clearTimeout(timeout);

          if (resp.ok) {
            const text = await resp.text();
            let parsed = null;
            try {
              parsed = JSON.parse(text);
            } catch {
              parsed = text;
            }
            return {
              id: item.id,
              name: item.name,
              success: true,
              activeUrl: targetUrl,
              data: parsed,
              isMirror: targetUrl !== item.primaryUrl,
            };
          } else {
            lastError = `HTTP ${resp.status}`;
          }
        } catch (e: any) {
          lastError = e.name === 'AbortError' ? '超时' : e.message;
        }
      }

      return {
        id: item.id,
        name: item.name,
        success: false,
        error: lastError || '无法从提供的 URL 获取节点配置',
      };
    })
  );

  const formatted = results.map((r) => (r.status === 'fulfilled' ? r.value : { success: false, error: '执行失败' }));
  return res.json({ success: true, results: formatted });
});

async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    // In dev mode, mount Vite middlewares
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    // Serve static files in production
    app.use(express.static(path.join(__dirname, 'dist')));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
  });
}

startServer();
