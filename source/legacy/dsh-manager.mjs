#!/usr/bin/env node
/**
 * DSH 对话管理器（控制台版）
 *
 * 列出 DSH 的工作区与对话（文件树 + 编号），支持按编号删除对话、
 * 删除工作区登记、或连同工作区里的对话一起删除，最后重启 DSH。
 *
 * 用法：双击 DSHManager.exe，或 node dsh-manager.mjs
 * 环境变量：
 *   DSH_HOME              覆盖 ~/.dsh 的位置（测试用沙盒）
 *   DSH_MANAGER_NO_RESTART=1  删除后不重启 DSH（测试用）
 *   DSH_MANAGER_EXE      指定 DeepSeek Harness.exe 路径（非默认安装位置时）
 */

import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import zlib from "node:zlib";
import readline from "node:readline";
import { execFileSync, spawn } from "node:child_process";

const HOME = process.env.USERPROFILE || os.homedir();
const DSH_HOME = process.env.DSH_HOME || path.join(HOME, ".dsh");
const SESSIONS_DIR = path.join(DSH_HOME, "sessions");
const STORAGES_DIR = path.join(DSH_HOME, "storages");
const WORKSPACE_JSON = path.join(STORAGES_DIR, "workspace.json");
const PROJCACHE_DIR = path.join(STORAGES_DIR, "session_projcache", "sessions");

const COLOR = process.stdout.isTTY;
const c = {
  dim: (s) => (COLOR ? `\x1b[2m${s}\x1b[0m` : s),
  bold: (s) => (COLOR ? `\x1b[1m${s}\x1b[0m` : s),
  cyan: (s) => (COLOR ? `\x1b[36m${s}\x1b[0m` : s),
  green: (s) => (COLOR ? `\x1b[32m${s}\x1b[0m` : s),
  red: (s) => (COLOR ? `\x1b[31m${s}\x1b[0m` : s),
  yellow: (s) => (COLOR ? `\x1b[33m${s}\x1b[0m` : s),
};

/* ------------------------------------------------------------------ */
/* zstd 多帧日志读取                                                    */
/* ------------------------------------------------------------------ */

function scanZstdFrames(buf) {
  const frames = [];
  let off = 0;
  while (off + 4 <= buf.length) {
    if (buf.readUInt32LE(off) !== 0xfd2fb528) break;
    let p = off + 4;
    const fhd = buf[p++];
    const fcsFlag = fhd >> 6;
    const single = (fhd >> 5) & 1;
    const checksum = (fhd >> 2) & 1;
    const dictFlag = fhd & 3;
    if (!single) p += 1;
    p += [0, 1, 2, 4][dictFlag];
    p += fcsFlag === 0 ? (single ? 1 : 0) : fcsFlag === 1 ? 2 : fcsFlag === 2 ? 4 : 8;
    let last = false;
    let ok = true;
    while (!last) {
      if (p + 3 > buf.length) { ok = false; break; }
      const bh = buf[p] | (buf[p + 1] << 8) | (buf[p + 2] << 16);
      p += 3;
      last = (bh & 1) === 1;
      const type = (bh >> 1) & 3;
      const size = bh >>> 3;
      if (type === 0 || type === 2) p += size;
      else if (type === 1) p += 1;
      else { ok = false; break; }
    }
    if (!ok || p > buf.length) break;
    if (checksum) p += 4;
    frames.push({ start: off, end: Math.min(p, buf.length) });
    off = p;
  }
  return frames;
}

function readSessionFacts(logPath) {
  const buf = fs.readFileSync(logPath);
  const chunks = [];
  for (const f of scanZstdFrames(buf)) {
    try {
      chunks.push(zlib.zstdDecompressSync(buf.subarray(f.start, f.end)));
    } catch {
      break;
    }
  }
  const facts = { id: "", cwd: "", title: "", lastTime: 0 };
  for (const line of Buffer.concat(chunks).toString("utf8").split("\n")) {
    if (!line) continue;
    let e;
    try { e = JSON.parse(line); } catch { continue; }
    if (e.type === "session") { facts.id = e.id || ""; facts.cwd = e.cwd || ""; }
    if (e.type === "session/title" && e.data && e.data.title) facts.title = e.data.title;
    if (typeof e.time === "number") facts.lastTime = Math.max(facts.lastTime, e.time);
  }
  return facts;
}

/* ------------------------------------------------------------------ */
/* 数据扫描                                                             */
/* ------------------------------------------------------------------ */

function scanSessions() {
  const out = [];
  if (!fs.existsSync(SESSIONS_DIR)) return out;
  for (const project of fs.readdirSync(SESSIONS_DIR, { withFileTypes: true })) {
    if (!project.isDirectory()) continue;
    const projectDir = path.join(SESSIONS_DIR, project.name);
    let entries;
    try { entries = fs.readdirSync(projectDir, { withFileTypes: true }); } catch { continue; }
    for (const dir of entries) {
      if (!dir.isDirectory() || !dir.name.startsWith("session-")) continue;
      const sessionDir = path.join(projectDir, dir.name);
      let files;
      try { files = fs.readdirSync(sessionDir); } catch { continue; }
      const logName = files.find((f) => f.startsWith("session.v") && f.endsWith(".jsonl.zstd"));
      if (!logName) continue;
      const logPath = path.join(sessionDir, logName);
      let stat;
      try { stat = fs.statSync(logPath); } catch { continue; }
      let facts = { id: dir.name, cwd: "", title: "", lastTime: 0 };
      try { facts = { ...facts, ...readSessionFacts(logPath) }; } catch { /* 读不出就用目录名 */ }
      out.push({
        id: facts.id || dir.name,
        dirName: dir.name,
        dir: sessionDir,
        cwd: facts.cwd,
        title: facts.title,
        lastTime: facts.lastTime || stat.mtimeMs,
        bytes: stat.size,
      });
    }
  }
  return out;
}

function loadStore() {
  const raw = fs.readFileSync(WORKSPACE_JSON, "utf8").replace(/^\uFEFF/, "");
  return JSON.parse(raw);
}

function normPath(p) {
  if (!p) return "";
  return path.resolve(p).replace(/[\\/]+$/, "").toLowerCase();
}

function letterFor(index) {
  let n = index;
  let s = "";
  do {
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return s;
}

function relTime(ms) {
  const diff = Date.now() - ms;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min}分钟前`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}小时前`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}天前`;
  const mo = Math.floor(d / 30);
  if (mo < 12) return `${mo}个月前`;
  return `${Math.floor(mo / 12)}年前`;
}

function displayWidth(text) {
  let w = 0;
  for (const ch of text) {
    const code = ch.codePointAt(0);
    w += (code >= 0x1100 && (
      code <= 0x115f || code === 0x2329 || code === 0x232a ||
      (code >= 0x2e80 && code <= 0xa4cf && code !== 0x303f) ||
      (code >= 0xac00 && code <= 0xd7a3) ||
      (code >= 0xf900 && code <= 0xfaff) ||
      (code >= 0xfe30 && code <= 0xfe6f) ||
      (code >= 0xff00 && code <= 0xff60) ||
      (code >= 0xffe0 && code <= 0xffe6)
    )) ? 2 : 1;
  }
  return w;
}

function padRight(text, width) {
  return text + " ".repeat(Math.max(0, width - displayWidth(text)));
}

function buildModel() {
  const store = loadStore();
  const sessions = scanSessions();
  const byId = new Map(sessions.map((s) => [s.id, s]));
  const assigned = new Set();
  const groups = [];

  for (const wsId of store.global.workspaceIds || []) {
    const rec = store.tables && store.tables.workspaces ? store.tables.workspaces[wsId] : undefined;
    if (!rec) continue;
    const listed = new Set(rec.sessionIds || []);
    const members = [];
    for (const s of sessions) {
      if (assigned.has(s.id)) continue;
      if (listed.has(s.id) || (s.cwd && normPath(s.cwd) === normPath(rec.path))) {
        members.push(s);
        assigned.add(s.id);
      }
    }
    members.sort((a, b) => b.lastTime - a.lastTime);
    groups.push({
      kind: "workspace",
      id: wsId,
      title: rec.title || path.basename(rec.path || ""),
      path: rec.path || "",
      members,
      isDefault: store.global.defaultWorkspaceId === wsId,
    });
  }

  const stray = sessions.filter((s) => !assigned.has(s.id)).sort((a, b) => b.lastTime - a.lastTime);
  if (stray.length > 0) {
    groups.push({ kind: "ungrouped", id: null, title: "未分组", path: "", members: stray, isDefault: false });
  }

  groups.forEach((g, i) => {
    g.letter = letterFor(i);
    g.members.forEach((m, j) => { m.number = j + 1; m.group = g; });
  });

  return { store, groups, byId };
}

/* ------------------------------------------------------------------ */
/* 显示                                                                 */
/* ------------------------------------------------------------------ */

function render(model) {
  const total = model.groups.reduce((n, g) => n + g.members.length, 0);
  console.log("");
  console.log(c.bold("================ DSH 对话管理器 ================"));
  console.log(c.dim(` 存储位置: ${DSH_HOME}`));
  console.log(c.dim(` 工作区 ${model.groups.length} 个 · 对话 ${total} 个`));
  console.log("");
  if (model.groups.length === 0) {
    console.log("  （没有任何工作区或对话）");
    console.log("");
    return;
  }

  const titleWidth = Math.min(
    46,
    Math.max(12, ...model.groups.flatMap((g) => g.members.map((m) => displayWidth(m.title || "(未命名)")))) + 2,
  );

  for (const g of model.groups) {
    const count = g.members.length;
    const name = g.kind === "ungrouped" ? "未分组" : g.title === "default-workspace" ? "默认工作区" : g.title;
    const tag = g.kind === "ungrouped" ? c.yellow(name) : c.cyan(name);
    const where = g.kind === "ungrouped" ? "" : c.dim(`  ${g.path}`);
    console.log(`${c.bold(g.letter)}  ${tag}${where}  ${c.dim(`(${count} 个对话)`)}`);
    if (count === 0) {
      console.log(c.dim("      （无对话）"));
    } else {
      for (const m of g.members) {
        const title = m.title || "(未命名)";
        console.log(`      ---${m.number}. ${padRight(title, titleWidth)}${c.dim(relTime(m.lastTime))}`);
      }
    }
    console.log("");
  }

  console.log(c.dim(" 输入示例：A1 | A1,A2 | B | B-all | r 重新扫描 | q 退出"));
}

/* ------------------------------------------------------------------ */
/* 输入解析                                                             */
/* ------------------------------------------------------------------ */

function findGroup(model, letter) {
  return model.groups.find((g) => g.letter === letter);
}

function parseCommand(line, model) {
  const plan = { sessions: new Set(), workspaces: new Set(), ungroupedAll: false, errors: [], notes: [] };
  const tokens = line.split(/[,，、\s]+/).filter(Boolean);
  if (tokens.length === 0) plan.errors.push("没有输入内容");

  for (const raw of tokens) {
    const token = raw.toUpperCase();
    const allMatch = /^([A-Z]+)-ALL$/.exec(token);
    const numMatch = /^([A-Z]+)(\d+)$/.exec(token);
    const groupMatch = /^([A-Z]+)$/.exec(token);

    if (allMatch) {
      const g = findGroup(model, allMatch[1]);
      if (!g) { plan.errors.push(`没有 ${allMatch[1]} 这个工作区`); continue; }
      if (g.kind === "ungrouped") {
        plan.ungroupedAll = true;
      } else {
        plan.workspaces.add(g.id);
      }
      for (const m of g.members) plan.sessions.add(m.id);
      continue;
    }

    if (numMatch) {
      const g = findGroup(model, numMatch[1]);
      if (!g) { plan.errors.push(`没有 ${numMatch[1]} 这个工作区`); continue; }
      const idx = Number(numMatch[2]);
      const member = g.members[idx - 1];
      if (!member) { plan.errors.push(`工作区 ${numMatch[1]} 没有第 ${idx} 个对话`); continue; }
      plan.sessions.add(member.id);
      continue;
    }

    if (groupMatch) {
      const g = findGroup(model, groupMatch[1]);
      if (!g) { plan.errors.push(`没有 ${groupMatch[1]} 这个工作区`); continue; }
      if (g.kind === "ungrouped") {
        plan.errors.push("“未分组”不是注册工作区，不能删除；清空它请用 " + g.letter + "-all");
        continue;
      }
      if (g.isDefault) {
        plan.notes.push(`${g.letter}「${g.title}」是 DSH 的默认工作区，删除后 DSH 不会自动重建它。`);
      }
      plan.workspaces.add(g.id);
      continue;
    }

    plan.errors.push(`无法识别的输入：${raw}`);
  }

  return plan;
}

/* ------------------------------------------------------------------ */
/* 确认与执行                                                           */
/* ------------------------------------------------------------------ */

function describePlan(plan, model) {
  const lines = [];
  for (const wsId of plan.workspaces) {
    const g = model.groups.find((x) => x.id === wsId);
    const keep = g.members.length;
    const allGone = keep > 0 && g.members.every((m) => plan.sessions.has(m.id));
    if (allGone) {
      lines.push(`删除工作区 ${g.letter}「${g.title}」的登记，并删除其中全部 ${keep} 个对话（文件夹保留）`);
    } else {
      lines.push(`删除工作区 ${g.letter}「${g.title}」的登记（文件夹保留${keep > 0 ? `，其中 ${keep} 个对话保留并移入未分组` : ""}）`);
    }
  }
  for (const id of plan.sessions) {
    const m = model.byId.get(id);
    if (!m) continue;
    if (plan.workspaces.has(m.group.id)) continue;
    if (plan.ungroupedAll && m.group.kind === "ungrouped") continue;
    lines.push(`删除对话 ${m.group.letter}${m.number}「${m.title || "(未命名)"}」（记录不可恢复）`);
  }
  if (plan.ungroupedAll) {
    const g = model.groups.find((x) => x.kind === "ungrouped");
    lines.push(`删除“未分组”中的全部 ${g.members.length} 个对话（记录不可恢复）`);
  }
  return lines;
}

function backupWorkspaceJson() {
  const stamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
  const dst = path.join(STORAGES_DIR, `workspace.json.bak-${stamp}`);
  fs.copyFileSync(WORKSPACE_JSON, dst);
  return dst;
}

function writeWorkspaceJson(store) {
  const tmp = WORKSPACE_JSON + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(store, null, 2) + "\n", "utf8");
  fs.renameSync(tmp, WORKSPACE_JSON);
}

function removeSessionFiles(session) {
  fs.rmSync(session.dir, { recursive: true, force: true });
  const cache = path.join(PROJCACHE_DIR, `${session.id}.json`);
  if (fs.existsSync(cache)) fs.rmSync(cache, { force: true });
}

function hintFor(error) {
  const code = error && error.code;
  if (code === "EPERM" || code === "EBUSY" || code === "EACCES") {
    return "文件被占用——该对话正在 DSH 中打开，请先在 DSH 里切换到别的对话或退出 DSH";
  }
  return (error && error.message) || String(error);
}

function executePlan(plan, model) {
  const result = { deleted: [], failed: [], workspaceNames: [], backup: "" };

  for (const wsId of plan.workspaces) {
    const g = model.groups.find((x) => x.id === wsId);
    if (g) result.workspaceNames.push(`${g.letter}「${g.title}」`);
  }

  for (const id of plan.sessions) {
    const m = model.byId.get(id);
    if (!m) continue;
    try {
      removeSessionFiles(m);
      result.deleted.push(`对话 ${m.group.letter}${m.number}「${m.title || "(未命名)"}」`);
    } catch (error) {
      result.failed.push(`对话 ${m.group.letter}${m.number}「${m.title || "(未命名)"}」：${hintFor(error)}`);
    }
  }

  const store = model.store;
  let changed = false;

  for (const wsId of plan.workspaces) {
    if (store.tables.workspaces[wsId]) {
      delete store.tables.workspaces[wsId];
      changed = true;
    }
    store.global.workspaceIds = (store.global.workspaceIds || []).filter((x) => x !== wsId);
  }

  const gone = new Set([...plan.sessions]);
  if (plan.sessions.size > 0) {
    for (const rec of Object.values(store.tables.workspaces || {})) {
      if (Array.isArray(rec.sessionIds) && rec.sessionIds.some((id) => gone.has(id))) {
        rec.sessionIds = rec.sessionIds.filter((id) => !gone.has(id));
        changed = true;
      }
    }
    for (const key of ["archivedSessionIds", "pinnedSessionIds"]) {
      const list = store.global[key];
      if (Array.isArray(list) && list.some((id) => gone.has(id))) {
        store.global[key] = list.filter((id) => !gone.has(id));
        changed = true;
      }
    }
  }

  if (changed) {
    result.backup = backupWorkspaceJson();
    writeWorkspaceJson(store);
  }

  return result;
}

/* ------------------------------------------------------------------ */
/* 重启 DSH                                                            */
/* ------------------------------------------------------------------ */

const DSH_IMAGE = "DeepSeek Harness.exe";

function findDshExe() {
  if (process.env.DSH_MANAGER_EXE && fs.existsSync(process.env.DSH_MANAGER_EXE)) {
    return process.env.DSH_MANAGER_EXE;
  }
  const candidates = [
    path.join(HOME, "AppData", "Local", "Programs", "DeepSeek Harness", "DeepSeek Harness.exe"),
    "C:\\Program Files\\DeepSeek Harness\\DeepSeek Harness.exe",
  ];
  for (const p of candidates) if (fs.existsSync(p)) return p;
  return "";
}

/* 用 tasklist 查同名进程的 PID；查询失败（沙盒/权限）时返回空数组。 */
function listDshPids() {
  try {
    const out = execFileSync("tasklist", ["/FI", `IMAGENAME eq ${DSH_IMAGE}`, "/FO", "CSV", "/NH"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      windowsHide: true,
    });
    return out
      .split(/\r?\n/)
      .map((line) => {
        const match = /^"([^"]+)","(\d+)"/.exec(line);
        return match ? Number(match[2]) : 0;
      })
      .filter((pid) => pid > 0);
  } catch {
    return [];
  }
}

/* 先起一个独立进程：等这些 PID 全部退出后再拉起 exe。
   取代原来的 ping -n 4 延时：不做固定等待，也不会在旧实例还活着时开出第二个。 */
function scheduleRelaunch(exe, pids) {
  const waiter = [
    'const { spawn } = require("node:child_process");',
    `const exe = ${JSON.stringify(exe)};`,
    `const pids = ${JSON.stringify(pids)};`,
    'const alive = (pid) => { try { process.kill(pid, 0); return true; } catch (e) { return e.code === "EPERM"; } };',
    "const deadline = Date.now() + 90000;",
    "(function poll() {",
    "  if (pids.some(alive)) {",
    "    if (Date.now() > deadline) process.exit(3);",
    "    return setTimeout(poll, 150);",
    "  }",
    '  try { spawn(exe, [], { detached: true, stdio: "ignore", windowsHide: true }).unref(); } catch (e) {}',
    "  setTimeout(() => process.exit(0), 1000);",
    "})();",
  ].join("\n");

  spawn(process.execPath, ["-e", waiter], { detached: true, stdio: "ignore", windowsHide: true }).unref();
}

/* 结束 DSH，失败时把退出码和 taskkill 原文一起带回来（原来被 stdio: ignore 吞掉了）。 */
function killDsh() {
  try {
    execFileSync("taskkill", ["/F", "/IM", DSH_IMAGE], {
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    return { ok: true, code: 0, detail: "" };
  } catch (error) {
    const raw = `${decodeOutput(error.stdout)}${decodeOutput(error.stderr)}`.replace(/\s+/g, " ").trim();
    return { ok: false, code: error.status, detail: raw };
  }
}

function decodeOutput(buf) {
  if (!buf) return "";
  const data = Buffer.isBuffer(buf) ? buf : Buffer.from(String(buf));
  if (data.length === 0) return "";
  try {
    return new TextDecoder("gbk").decode(data);
  } catch {
    return data.toString("utf8");
  }
}

/* 权限不够时，借 UAC 提权再关一次。 */
function killDshElevated() {
  try {
    execFileSync(
      "powershell.exe",
      ["-NoProfile", "-Command", "Start-Process -FilePath taskkill -ArgumentList '/F','/IM','\"DeepSeek Harness.exe\"' -Verb RunAs -Wait"],
      { stdio: "ignore", windowsHide: true, timeout: 60000 },
    );
    return true;
  } catch {
    return false;
  }
}

async function restartDsh() {
  if (process.env.DSH_MANAGER_NO_RESTART === "1") {
    console.log(c.dim("\n[测试模式] 跳过重启 DSH。"));
    return;
  }
  const exe = findDshExe();
  if (!exe) {
    console.log(c.yellow("\n! 没找到 DeepSeek Harness.exe，请手动启动 DSH 让列表刷新。"));
    return;
  }

  const pids = listDshPids();
  console.log(c.dim(`\n正在重启 DeepSeek Harness …（检测到 ${pids.length} 个运行中的进程）`));

  if (pids.length === 0) {
    // 没有进程：可能是以网页/命令行方式（node dsh web）在跑，也可能确实没开
    const answer = (await ask(c.yellow("没有检测到运行中的 DeepSeek Harness.exe，现在直接启动吗？(y/N) "))).trim().toLowerCase();
    if (answer === "y" || answer === "yes") {
      try {
        spawn(exe, [], { detached: true, stdio: "ignore", windowsHide: true }).unref();
        console.log(c.green("已启动 DSH。"));
      } catch (error) {
        console.log(c.yellow(`启动失败：${error.message}。请手动打开 DSH。`));
      }
    } else {
      console.log(c.dim("已跳过。若 DSH 是以网页/命令行方式运行的，刷新页面即可看到最新列表。"));
    }
    return;
  }

  // 先排队再杀：这样即使本程序随 DSH 一起被结束，DSH 也会被重新拉起
  scheduleRelaunch(exe, pids);

  const killed = killDsh();
  if (killed.ok) {
    console.log(c.green("DSH 已关闭，正在自动重新启动 …"));
    console.log(c.dim("（本窗口如果没关，可以按回车退出）"));
    return;
  }

  const code = killed.code === undefined || killed.code === null ? "?" : killed.code;
  console.log(c.yellow(`自动重启失败：关闭 DSH 出错（exit ${code}）${killed.detail ? "：" + killed.detail : ""}`));
  if (code === 1 || /拒绝访问|Access is denied/i.test(killed.detail)) {
    console.log(c.dim("  原因多半是 DSH 以管理员权限运行，而本程序不是。"));
    const retry = (await ask(c.yellow("  要用管理员权限再关一次吗？会弹出 UAC 确认。(y/N) "))).trim().toLowerCase();
    if (retry === "y" || retry === "yes") {
      const elevated = killDshElevated();
      console.log(c.dim(elevated ? "  已请求管理员权限；DSH 被关闭后会在几秒内自动重新打开。" : "  提权失败，请手动以管理员身份关闭 DSH。"));
      return;
    }
  }
  console.log(c.yellow("请手动打开 DSH。"));
}

/* ------------------------------------------------------------------ */
/* 主流程                                                               */
/* ------------------------------------------------------------------ */

const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: Boolean(process.stdin.isTTY) });

/* 行缓冲：即使用户在渲染期间提前输入（或整段粘贴），也不会丢行 */
const queuedLines = [];
const waiting = [];
rl.on("line", (line) => {
  if (waiting.length > 0) waiting.shift()(line);
  else queuedLines.push(line);
});
rl.on("close", () => {
  while (waiting.length > 0) waiting.shift()("");
});

function ask(question) {
  if (question) process.stdout.write(question);
  if (queuedLines.length > 0) return Promise.resolve(queuedLines.shift());
  return new Promise((resolve) => waiting.push(resolve));
}

async function main() {
  if (!fs.existsSync(WORKSPACE_JSON)) {
    console.log(c.red(`找不到 ${WORKSPACE_JSON}，DSH 可能还没初始化。`));
    await ask("按回车键退出…");
    return;
  }

  let model = buildModel();
  for (;;) {
    render(model);
    const line = (await ask(c.bold("请输入: "))).trim();

    if (!line) continue;
    if (/^[qQ]$/.test(line)) { rl.close(); return; }
    if (/^[rR]$/.test(line)) { model = buildModel(); continue; }

    const plan = parseCommand(line, model);
    if (plan.errors.length > 0) {
      console.log("");
      for (const e of plan.errors) console.log(c.red(`  ✗ ${e}`));
      continue;
    }
    if (plan.sessions.size === 0 && plan.workspaces.size === 0) {
      console.log(c.yellow("\n  没有选中任何要删除的内容。"));
      continue;
    }

    console.log("");
    console.log(c.bold(" 即将执行："));
    for (const n of plan.notes) console.log(c.yellow(`  ! ${n}`));
    for (const l of describePlan(plan, model)) console.log(`  · ${l}`);
    console.log("");

    const answer = (await ask(c.bold(" 是否删除 y是 n否: "))).trim().toLowerCase();
    if (answer !== "y" && answer !== "yes") {
      console.log(c.dim("\n 已取消，未做任何修改。"));
      continue;
    }

    console.log("");
    const result = executePlan(plan, model);
    for (const d of result.deleted) console.log(c.green(`  ✓ 已删除${d}`));
    for (const f of result.failed) console.log(c.red(`  ✗ 删除失败 ${f}`));
    if (result.workspaceNames.length > 0) {
      console.log(c.green(`  ✓ 已移除工作区登记 ${result.workspaceNames.join("、")}`));
    }
    if (result.backup) console.log(c.dim(`  已备份 workspace.json → ${result.backup}`));

    await restartDsh();
    await ask(c.dim("\n按回车键关闭窗口…"));
    rl.close();
    return;
  }
}

main().catch((error) => {
  console.log(c.red(`\n出错了：${error && error.stack ? error.stack : error}`));
  ask("按回车键退出…").then(() => process.exit(1));
});
