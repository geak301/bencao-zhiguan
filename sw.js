/**
 * 本草智管 PWA Service Worker
 * 支持离线缓存和应用更新
 */

const CACHE_NAME = 'bencao-zhiguan-v5.0';
const APP_VERSION = '5.0.0';

// 需要预缓存的核心资源
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/dashboard.html',
  '/assistant.html',
  '/prescriptions.html',
  '/herbs.html',
  '/data-board.html',
  '/purchase.html',
  '/replenish.html',
  '/stock-flow.html',
  '/users.html',
  '/logs.html',
  '/manifest.json',
  '/icon-192x192.png',
  '/icon-512x512.png',
  '/favicon.ico',
  'https://cdn.tailwindcss.com',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js'
];

// 安装事件：预缓存核心资源
self.addEventListener('install', (event) => {
  console.log('[Service Worker] 安装中，版本:', APP_VERSION);
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[Service Worker] 预缓存核心资源');
        // 缓存所有资源，失败的不影响整体
        return Promise.allSettled(
          PRECACHE_URLS.map(url => 
            cache.add(url).catch(err => {
              console.log('[Service Worker] 缓存失败:', url, err);
            })
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});

// 激活事件：清理旧缓存
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] 激活中');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter(name => name !== CACHE_NAME)
            .map(name => {
              console.log('[Service Worker] 删除旧缓存:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => self.clients.claim())
  );
});

// 请求拦截：缓存优先策略
self.addEventListener('fetch', (event) => {
  const request = event.request;
  
  // 只处理GET请求
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);
  
  // API请求不缓存，直接网络请求
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() => {
        // API请求失败时返回离线提示
        return new Response(JSON.stringify({
          success: false,
          message: '网络连接失败，请检查网络后重试',
          offline: true
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }

  // 静态资源：缓存优先，网络更新
  if (url.origin === self.location.origin || 
      url.href.includes('cdn.tailwindcss.com') ||
      url.href.includes('cdnjs.cloudflare.com') ||
      url.href.includes('cdn.jsdelivr.net')) {
    
    event.respondWith(
      caches.match(request)
        .then((cachedResponse) => {
          if (cachedResponse) {
            // 缓存命中，返回缓存，同时后台更新
            event.waitUntil(
              fetch(request)
                .then((networkResponse) => {
                  if (networkResponse && networkResponse.status === 200) {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then(cache => {
                      cache.put(request, responseClone);
                    });
                  }
                })
                .catch(() => {})
            );
            return cachedResponse;
          }
          
          // 缓存未命中，网络请求
          return fetch(request)
            .then((networkResponse) => {
              if (networkResponse && networkResponse.status === 200) {
                const responseClone = networkResponse.clone();
                event.waitUntil(
                  caches.open(CACHE_NAME).then(cache => {
                    cache.put(request, responseClone);
                  })
                );
              }
              return networkResponse;
            })
            .catch(() => {
              // 网络失败，返回离线页面
              if (request.mode === 'navigate') {
                return caches.match('/index.html');
              }
              return new Response('离线状态', { status: 503 });
            });
        })
    );
  }
});

// 监听来自客户端的消息
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data === 'GET_VERSION') {
    event.source.postMessage({
      type: 'VERSION',
      version: APP_VERSION,
      cacheName: CACHE_NAME
    });
  }
});

console.log('[Service Worker] 已加载，版本:', APP_VERSION);
