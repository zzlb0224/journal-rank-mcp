---
name: search-scispace
description: |
  通过 patchright-cli 自动化操作 scispace.com 网站，实现登录等待、关键词搜索、滚动加载、结果筛选与信息提取。
  返回作者、年份、标题、DOI、sort_imf 等引用信息。
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
metadata:
  source: 项目内建
---

# search-scispace

通过 patchright-cli 驱动浏览器自动化操作 [scispace.com](https://scispace.com)，提取论文引用信息。

## 工作流

### Step 1: 打开网站并等待用户登录

```bash
patchright-cli open "https://scispace.com" --persistent
patchright-cli snapshot
```

等待用户手动登录并进行操作，直到页面出现 `.srankInfo` 和 `#_zlb_root_div_` 元素:

```bash
patchright-cli wait-for .srankInfo
patchright-cli wait-for "#_zlb_root_div_"
```

中间用户可能刷新网页，刷新后重新等待:

```bash
patchright-cli wait-for .srankInfo
patchright-cli wait-for "#_zlb_root_div_"
```

### Step 2: 根据关键词打开搜索 URL

默认搜索高水平期刊 + 2024年以来的论文:

```bash
patchright-cli goto "https://scispace.com/search?is_top_publication=true&year=2024%2C&q=<URL_ENCODED_KEYWORD>"
patchright-cli wait 3000
```

**参数说明**:
- `is_top_publication=true` — 仅搜索高水平期刊
- `year=2024%2C` — 2024年至今（`%2C` 是逗号，表示范围起始）
- 如果用户要求不限定年份，去掉 `&year=2024%2C`
- 如果用户指定特定年份（如 2020），改为 `&year=2020%2C`
- 如果用户指定年份区间（如 2020-2023），改为 `&year=2020%2C2023`

### Step 3: 慢慢滚动并等待加载完成（合并筛选）

滚动过程中检查 `#sidebar-inset-container table tr` 中可见行的第2列(`td[1]`)和第3列(`td[2]`)是否由空白变为超过10个字。满足以下任一条件即停止:
- 有 **5 条**可见行同时满足两列都有 >10 字
- **所有可见行**的两列都已出现文字

```bash
patchright-cli run-code --code="
const delay = ms => new Promise(r => setTimeout(r, ms));
const step = window.innerHeight / 2;
const MAX_ITERATIONS = 60; // 防无限循环

for (let iter = 0; iter < MAX_ITERATIONS; iter++) {
  const allRows = document.querySelectorAll('#sidebar-inset-container table tr');
  const visibleRows = [];
  allRows.forEach(row => {
    const style = window.getComputedStyle(row);
    if (style.display !== 'none' && style.visibility !== 'hidden') {
      visibleRows.push(row);
    }
  });

  let colsReadyCount = 0;
  let allHaveText = true;
  const readyRows = [];

  visibleRows.forEach((row, i) => {
    const cells = row.querySelectorAll('td');
    if (cells.length < 3) return;
    const col2 = cells[1].textContent.trim();
    const col3 = cells[2].textContent.trim();
    const bothReady = col2.length > 10 && col3.length > 10;
    if (bothReady) {
      colsReadyCount++;
      readyRows.push(row);
    }
    if (!bothReady) allHaveText = false;
  });

  console.log('iter', iter, '- visible:', visibleRows.length, 'ready:', colsReadyCount, 'allHaveText:', allHaveText);

  if (colsReadyCount >= 5 || allHaveText) {
    console.log('条件满足，停止滚动');
    break;
  }

  // 继续往下滚动
  const currentScroll = window.scrollY;
  window.scrollTo(0, currentScroll + step);
  await delay(1000);
}

// 等剩余内容稳定
await delay(2000);
window.scrollTo(0, document.body.scrollHeight);
await delay(2000);
"
```

### Step 4: 提取引用信息

从符合条件的可见行中提取前 5 条的作者、年份、标题、DOI、期刊名称、`.sort_imf`:

```bash
patchright-cli run-code --code="
const allRows = document.querySelectorAll('#sidebar-inset-container table tr');
const results = [];

allRows.forEach(row => {
  const style = window.getComputedStyle(row);
  if (style.display === 'none' || style.visibility === 'hidden') return;
  if (results.length >= 5) return;

  const cells = row.querySelectorAll('td');
  if (cells.length < 3) return;
  const col2 = cells[1].textContent.trim();
  const col3 = cells[2].textContent.trim();
  if (col2.length <= 10 || col3.length <= 10) return;

  const firstTd = cells[0];

  // 标题: div[data-element=\"publication_name\"] a
  const titleEl = firstTd.querySelector('div[data-element=\"publication_name\"] a');
  const title = titleEl ? titleEl.textContent.trim() : '';

  // DOI: a[href^=\"https://doi.org/\"]
  const doiEl = firstTd.querySelector('a[href^=\"https://doi.org/\"]');
  const doi = doiEl ? doiEl.textContent.trim() : '';

  // 作者: .paperContributors_author_list__CaFpW 下的作者 span
  const authorEls = firstTd.querySelectorAll('.paperContributors_author_list__CaFpW span.text-xs.no-underline');
  const author = authorEls.length ? Array.from(authorEls).map(el => el.textContent.trim()).join(', ') : '';

  // 年份: .info-box 第一个 span.text-typo-secondary.text-sm（格式如 \"22 Jan 2026\"），取最后4位
  const dateEl = firstTd.querySelector('.info-box > span.text-typo-secondary.text-sm');
  const dateText = dateEl ? dateEl.textContent.trim() : '';
  const year = dateText.length >= 4 ? dateText.slice(-4) : '';

  // 期刊名称: .info-box a[href^=\"/journals/\"]
  const journalEl = firstTd.querySelector('.info-box a[href^=\"/journals/\"]');
  const journal = journalEl ? journalEl.textContent.trim() : '';

  // sort_imf: 取 value 属性（如 \"13.3\"）
  const sortImfEl = firstTd.querySelector('.srankInfo.sort_imf');
  const sort_imf = sortImfEl ? (sortImfEl.getAttribute('value') || sortImfEl.textContent.trim()) : '';

  results.push({ author, year, title, doi, journal, sort_imf });
});

console.log(JSON.stringify(results, null, 2));
"
```

输出格式（JSON 数组）:

```json
[
  {
    "author": "Lei Shen, Qingyue Shi, Debadrita Panda, Vinit Parida",
    "year": "2026",
    "title": "Digital technology diffusion through supply chain orchestration",
    "doi": "10.1016/j.techfore.2026.124554",
    "journal": "Technological Forecasting and Social Change",
    "sort_imf": "13.3"
  }
]
```

## 完整自动化脚本示例

将 1-4 步合并为单次执行（登录等待除外）:

```bash
# === Step 1: 打开网站，用户手动登录 ===
patchright-cli open "https://scispace.com" --persistent
patchright-cli wait-for .srankInfo
patchright-cli wait-for "#_zlb_root_div_"

# === Step 2: 搜索关键词（默认高水平期刊+2024年起）===
patchright-cli goto "https://scispace.com/search?is_top_publication=true&year=2024%2C&q=machine+learning"
patchright-cli wait 3000

# === Step 3: 滚动 + 检查第2/3列有>10字（5条达标或全部就绪即停）===
patchright-cli run-code --code="
const delay = ms => new Promise(r => setTimeout(r, ms));
const step = window.innerHeight / 2;

for (let iter = 0; iter < 60; iter++) {
  const allRows = document.querySelectorAll('#sidebar-inset-container table tr');
  const visibleRows = [];
  allRows.forEach(row => {
    const style = window.getComputedStyle(row);
    if (style.display !== 'none' && style.visibility !== 'hidden') {
      visibleRows.push(row);
    }
  });

  let colsReadyCount = 0;
  let allHaveText = true;

  visibleRows.forEach(row => {
    const cells = row.querySelectorAll('td');
    if (cells.length < 3) return;
    if (cells[1].textContent.trim().length > 10 && cells[2].textContent.trim().length > 10) {
      colsReadyCount++;
    } else {
      allHaveText = false;
    }
  });

  console.log('iter', iter, 'visible:', visibleRows.length, 'ready:', colsReadyCount, 'allHaveText:', allHaveText);

  if (colsReadyCount >= 5 || allHaveText) break;

  window.scrollTo(0, window.scrollY + step);
  await delay(1000);
}

await delay(2000);
window.scrollTo(0, document.body.scrollHeight);
await delay(2000);
"

# === Step 4: 提取前5条引用信息 ===
patchright-cli run-code --code="
const allRows = document.querySelectorAll('#sidebar-inset-container table tr');
const results = [];

allRows.forEach(row => {
  const style = window.getComputedStyle(row);
  if (style.display === 'none' || style.visibility === 'hidden') return;
  if (results.length >= 5) return;

  const cells = row.querySelectorAll('td');
  if (cells.length < 3) return;
  if (cells[1].textContent.trim().length <= 10 || cells[2].textContent.trim().length <= 10) return;

  const firstTd = cells[0];
  const titleEl = firstTd.querySelector('div[data-element=\"publication_name\"] a');
  const doiEl = firstTd.querySelector('a[href^=\"https://doi.org/\"]');
  const authorEls = firstTd.querySelectorAll('.paperContributors_author_list__CaFpW span.text-xs.no-underline');
  const dateEl = firstTd.querySelector('.info-box > span.text-typo-secondary.text-sm');
  const journalEl = firstTd.querySelector('.info-box a[href^=\"/journals/\"]');
  const sortImfEl = firstTd.querySelector('.srankInfo.sort_imf');

  results.push({
    author: authorEls.length ? Array.from(authorEls).map(e => e.textContent.trim()).join(', ') : '',
    year: dateEl ? dateEl.textContent.trim().slice(-4) : '',
    title: titleEl ? titleEl.textContent.trim() : '',
    doi: doiEl ? doiEl.textContent.trim() : '',
    journal: journalEl ? journalEl.textContent.trim() : '',
    sort_imf: sortImfEl ? (sortImfEl.getAttribute('value') || sortImfEl.textContent.trim()) : ''
  });
});

console.log(JSON.stringify(results, null, 2));
"
```

## 注意事项

- 字段提取选择器基于实际 DOM 结构确定，如果 Scispace 改版可能需要调整
- `--persistent` 参数保持登录状态，下次无需重新登录
- 如果中间刷新了网页，重新执行 `wait-for .srankInfo` 和 `wait-for #_zlb_root_div_`
- 如果搜索结果为空，请检查关键词或 URL 格式是否正确
