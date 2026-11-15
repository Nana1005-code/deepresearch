/**
 * 原文质检标注图层。
 *
 * 规范标注方式：在具体链接/句子处插入上标角标（[n] 或严重级符号），
 * 高亮样式可选（角标 / 下划线 / 底色），关闭开关时全部移除、DOM 复原。
 * 不修改 MarkdownDocument 组件，也不拦截事件。
 */
import type { QualityCitation, QualityIssue } from "../services/quality";

export type MarkerStyle = "sup" | "underline" | "fill";

const FLAG_CLASS = "rqg-flagged";
const FOCUS_CLASS = "rqg-focus";
const SENTENCE_CLASS = "rqg-sentence";
const FLASH_CLASS = "rqg-flash";
const BADGE_ATTR = "data-rqg-badge";
const STYLE_ATTR = "data-rqg-style";

export interface MarkerTarget {
  url?: string;
  quote?: string;
  snippet?: string;
  section?: string;
  line?: number;
  location_scope?: "start" | "end";
}

interface Located {
  block: HTMLElement;
  anchor?: HTMLAnchorElement;
}

function normalize(text: string): string {
  return text.replace(/\s+/g, "").trim();
}

function visibleText(text: string): string {
  const plain = text.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)/, "")
    .replace(/\*\*|__|`|\*/g, "");
  const decoder = document.createElement("textarea");
  decoder.innerHTML = plain;
  return normalize(decoder.value);
}

function urlKey(url: string): string {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
    const path = parsed.pathname.replace(/\/$/, "");
    const keys: string[] = [];
    parsed.searchParams.forEach((_value, key) => keys.push(key));
    for (const key of keys) {
      if (/^utm_/i.test(key) || ["fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "spm", "share_token", "from", "source"].includes(key.toLowerCase())) parsed.searchParams.delete(key);
    }
    parsed.searchParams.sort();
    return `${host}${parsed.port ? ':' + parsed.port : ''}${path}${parsed.searchParams.size ? '?' + parsed.searchParams.toString() : ''}`;
  } catch {
    return url.trim().toLowerCase();
  }
}

function resolveRoot(button: HTMLElement | null): HTMLElement | null {
  const card = button?.closest(".document-card");
  if (card) return card.querySelector<HTMLElement>(".markdown-body");
  return null;
}

function headingCandidates(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>("h1,h2,h3,h4,h5,h6"));
}

const BLOCK_SELECTOR = "p,li,blockquote,td,h1,h2,h3,h4,h5,h6";

function blockOf(node: Node | null, root: HTMLElement): HTMLElement | null {
  let current: Node | null = node;
  while (current && current !== root) {
    if (current instanceof HTMLElement && current.matches(BLOCK_SELECTOR)) return current;
    current = current.parentNode;
  }
  return null;
}

/** Scroll the reading pane only. scrollIntoView also scrolls overflow:hidden
 * ancestors, which can move the entire app without exposing a way back up. */
function scrollReadingPane(element: HTMLElement): void {
  let pane: HTMLElement | null = null;
  for (let ancestor = element.parentElement; ancestor; ancestor = ancestor.parentElement) {
    const overflow = getComputedStyle(ancestor).overflowY;
    if (!pane && /^(auto|scroll)$/.test(overflow) && ancestor.scrollHeight > ancestor.clientHeight + 1) {
      pane = ancestor;
    }
    // Recover offsets left behind by the previous scrollIntoView behaviour.
    if (overflow === "hidden" && ancestor.scrollTop) ancestor.scrollTop = 0;
  }
  const target = element.getBoundingClientRect();
  if (pane) {
    const viewport = pane.getBoundingClientRect();
    const header = pane.querySelector<HTMLElement>(":scope > .research-tabs, :scope > .comparison-header");
    const inset = header && getComputedStyle(header).position === "sticky" ? header.offsetHeight : 0;
    const available = pane.clientHeight - inset;
    const top = pane.scrollTop + target.top - viewport.top - pane.clientTop - inset
      - Math.max(0, (available - target.height) / 2);
    pane.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  } else if (document.documentElement.scrollHeight > window.innerHeight) {
    // Narrow layouts can use the document itself as the reading surface.
    window.scrollTo({ top: Math.max(0, window.scrollY + target.top - (window.innerHeight - Math.min(target.height, window.innerHeight)) / 2), behavior: "smooth" });
  }
}

export class QualityMarkerLayer {
  private root: HTMLElement | null;
  private style: MarkerStyle = "underline";
  private flagged: HTMLElement[] = [];
  private chips: HTMLElement[] = [];
  private originalClasses = new Map<HTMLElement, string | null>();
  private focus: { element: HTMLElement; className: string | null; timer: number } | null = null;
  private report = "";

  constructor(button: HTMLElement | null, style: MarkerStyle = "underline") {
    this.root = resolveRoot(button);
    this.style = style;
    this.applyStyle();
  }

  get available(): boolean {
    return this.root !== null;
  }

  setStyle(style: MarkerStyle): void {
    this.style = style;
    this.applyStyle();
  }

  private applyStyle(): void {
    if (this.root) this.root.setAttribute(STYLE_ATTR, this.style);
  }

  refresh(button: HTMLElement | null, report = ""): void {
    const nextRoot = resolveRoot(button);
    if (nextRoot !== this.root) this.clear();
    this.root = nextRoot;
    this.report = report;
  }

  /** 在具体链接/句子上插入角标：引用 [n]，问题用严重级符号。 */
  apply(issues: QualityIssue[], citations: QualityCitation[] = []): number {
    this.clear();
    if (!this.root) return 0;
    this.applyStyle();
    let count = 0;

    for (const citation of citations) {
      if (!citation.number) continue;
      const located = this.resolve({
        url: citation.url,
        quote: citation.quote,
        snippet: citation.snippet,
        section: citation.section,
        line: citation.line
      });
      if (!located) continue;
      this.insertChip(
        located,
        `[${citation.number}]`,
        "rqg-sup-chip",
        `引用 [${citation.number}]：${citation.title || citation.url}`
      );
      count += 1;
    }

    const used = new Set<HTMLElement>();
    for (const issue of issues) {
      const located = this.resolve({
        url: issue.url,
        quote: issue.quote,
        snippet: issue.snippet,
        section: issue.section,
        line: issue.line, location_scope: issue.location_scope
      });
      if (!located || used.has(located.block)) continue;
      used.add(located.block);
      this.originalClasses.set(located.block, located.block.getAttribute("class"));
      located.block.classList.add(FLAG_CLASS);
      this.flagged.push(located.block);
      this.insertChip(
        located,
        issue.severity === "error" ? "✕" : issue.severity === "warn" ? "!" : "i",
        "rqg-inline-badge",
        issue.message,
        issue.severity
      );
      count += 1;
    }
    return count;
  }

  private insertChip(
    located: Located,
    text: string,
    className: string,
    title: string,
    severity?: string
  ): void {
    const chip = document.createElement("span");
    chip.className = className;
    chip.setAttribute("data-rqg-label", text);
    chip.setAttribute("aria-label", text);
    chip.title = title;
    if (severity) chip.setAttribute(BADGE_ATTR, severity);
    const host = located.anchor || located.block;
    host.insertAdjacentElement("afterend", chip);
    this.chips.push(chip);
  }

  /** 精确定位：链接 → 句子 → 段落 → 章节。 */
  locate(target: MarkerTarget): boolean {
    this.clearFocus();
    if (!this.root) return false;
    const located = this.resolve(target);
    if (!located) return false;
    const element = located.anchor || located.block;
    const className = element.getAttribute("class");
    element.classList.add(FOCUS_CLASS, FLASH_CLASS);
    scrollReadingPane(element);
    const timer = window.setTimeout(() => {
      element.classList.remove(FLASH_CLASS);
    }, 2400);
    this.focus = { element, className, timer };
    return true;
  }

  private clearFocus(): void {
    if (!this.focus) return;
    const { element, className, timer } = this.focus;
    window.clearTimeout(timer);
    if (className === null) element.removeAttribute("class");
    else element.setAttribute("class", className);
    this.focus = null;
  }

  private resolve(target: MarkerTarget): Located | null {
    if (!this.root) return null;
    const headings = headingCandidates(this.root);
    const wanted = visibleText(target.section || "");
    const matching = wanted ? headings.filter(item => visibleText(item.textContent || "") === wanted) : [];
    let heading = matching[0];
    if (matching.length > 1 && target.line !== undefined) {
      const occurrence = this.report.split(/\r?\n/).slice(0, target.line + 1)
        .filter(line => /^#{1,6}\s/.test(line) && visibleText(line.replace(/^#{1,6}\s+/, "")) === wanted).length;
      heading = matching[Math.max(0, occurrence - 1)] || heading;
    }
    const nextHeading = heading && headings[headings.indexOf(heading) + 1];
    const blocks = Array.from(this.root.querySelectorAll<HTMLElement>(BLOCK_SELECTOR));
    const scoped = heading ? blocks.filter(block => block === heading ||
      ((heading.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0 &&
       (!nextHeading || (nextHeading.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_PRECEDING) !== 0))) : blocks;
    const rawLine = target.line === undefined ? "" : this.report.split(/\r?\n/)[target.line] || "";
    const texts = [target.quote, target.snippet, rawLine].filter(Boolean).map(text => visibleText(text!)).filter(text => text.length >= 3);
    // Match a rendered paragraph across strong/em/a nodes without rewriting its
    // DOM. Prefer the supplied sentence/section over the first identical URL.
    for (const candidates of [scoped, blocks]) {
      for (const text of texts) {
        const block = candidates.find(item => normalize(item.textContent || "").includes(text));
        if (block) {
          const anchor = target.url ? Array.from(block.querySelectorAll<HTMLAnchorElement>("a[href]"))
            .find(item => urlKey(item.getAttribute("href") || "") === urlKey(target.url!)) : undefined;
          return { block, anchor };
        }
      }
    }
    if (target.url) {
      const anchor = this.findAnchor(target.url, scoped) || this.findAnchor(target.url);
      if (anchor) return { block: blockOf(anchor, this.root) || anchor, anchor };
    }
    if (heading) return { block: target.location_scope === "end" ? scoped[scoped.length - 1] || heading : heading };
    if (target.location_scope) {
      const block = target.location_scope === "end" ? blocks[blocks.length - 1] : blocks[0];
      if (block) return { block };
    }
    return null;
  }

  private findAnchor(url: string, blocks?: HTMLElement[]): HTMLAnchorElement | null {
    if (!this.root) return null;
    const wanted = urlKey(url);
    const anchors = Array.from(this.root.querySelectorAll<HTMLAnchorElement>("a[href]"));
    return (
      anchors.find((anchor) => (!blocks || blocks.some(block => block.contains(anchor))) && urlKey(anchor.getAttribute("href") || "") === wanted) || null
    );
  }

  clear(): void {
    this.clearFocus();
    for (const chip of this.chips) chip.remove();
    this.chips = [];
    for (const element of this.flagged) {
      const original = this.originalClasses.get(element);
      if (original == null) element.removeAttribute("class");
      else element.setAttribute("class", original);
    }
    this.originalClasses.clear();
    this.flagged = [];
    if (this.root) {
      this.root.removeAttribute(STYLE_ATTR);
      this.root.querySelectorAll<HTMLElement>("[data-rqg-badge]").forEach((node) => node.remove());
      this.root
        .querySelectorAll<HTMLElement>(".rqg-sup-chip")
        .forEach((node) => node.remove());
    }
  }
}

export { FLAG_CLASS, FOCUS_CLASS, SENTENCE_CLASS, FLASH_CLASS };
