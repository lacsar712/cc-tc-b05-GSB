<script>
  export let session;
  export let isWriter;

  let briefings = [];
  let selected = null;
  let error = "";
  let loading = false;
  let generating = false;

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString();
  }

  async function loadList() {
    loading = true;
    error = "";
    try {
      const res = await fetch("/api/briefings", { headers: headers() });
      if (res.status === 401) {
        error = "登录已失效，请重新登录";
        return;
      }
      if (!res.ok) {
        error = "历史清单加载失败";
        return;
      }
      briefings = await res.json();
      if (selected && !briefings.some((b) => b.id === selected.id)) selected = null;
      if (!selected && briefings.length) await openBriefing(briefings[0].id);
    } catch {
      error = "无法连接接口";
    } finally {
      loading = false;
    }
  }

  async function openBriefing(id) {
    error = "";
    try {
      const res = await fetch(`/api/briefings/${id}`, { headers: headers() });
      if (!res.ok) {
        error = "简报读取失败";
        return;
      }
      selected = await res.json();
    } catch {
      error = "无法连接接口";
    }
  }

  async function generate() {
    if (!isWriter || generating) return;
    generating = true;
    error = "";
    try {
      const res = await fetch("/api/briefings", {
        method: "POST",
        headers: headers(),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "生成失败";
        return;
      }
      selected = data;
      await loadList();
      selected = data;
    } catch {
      error = "生成时网络异常";
    } finally {
      generating = false;
    }
  }

  loadList();
</script>

<section>
  <h2>生成按钮</h2>
  {#if isWriter}
    <button disabled={generating} on:click={generate}>
      {generating ? "生成中…" : "生成交班简报（冻结当班统计）"}
    </button>
    <p class="hint">
      按下瞬间的合格 / 超限 / 待办数量与最近几笔提要将冻结写入正文并入库，
      之后线上数据变动不影响已生成简报；二衬交班同走此份，不另开旁路。
    </p>
  {:else}
    <p class="hint">巡检员只读：可阅读已生成简报，不可点生成。</p>
  {/if}
  {#if error}<p class="err">{error}</p>{/if}
</section>

<section>
  <h2>
    历史清单
    <button class="secondary small" disabled={loading} on:click={loadList}>刷新</button>
  </h2>
  {#if briefings.length === 0}
    <p class="hint">{loading ? "加载中…" : "暂无已生成简报。"}</p>
  {:else}
    <ul class="briefing-list">
      {#each briefings as b}
        <li>
          <button
            class="link"
            class:current={selected && selected.id === b.id}
            on:click={() => openBriefing(b.id)}
          >
            第 {b.id} 号 · {fmtTime(b.generated_at)} · {b.generated_by}
          </button>
          <span class="counts">
            合格 {b.qualified_count} / 超限 {b.overlimit_count} / 待办 {b.pending_count}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<section>
  <h2>正文预览</h2>
  {#if selected}
    <pre class="briefing-body">{selected.body}</pre>
    <p class="hint">正文为生成瞬间冻结入库的内容，只读不可手改。</p>
  {:else}
    <p class="hint">从上方历史清单选择一份简报，查看冻结正文。</p>
  {/if}
</section>

<style>
  h2 {
    font-size: 1rem;
    color: #fbbf24;
    margin: 0 0 0.75rem;
  }
  .small {
    font-size: 0.75rem;
    padding: 0.2rem 0.6rem;
    font-weight: 400;
  }
  .hint {
    color: #a8a29e;
    font-size: 0.85rem;
    margin: 0.5rem 0 0;
  }
  .err {
    color: #fb7185;
  }
  .briefing-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .briefing-list li {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    flex-wrap: wrap;
    padding: 0.4rem 0;
    border-bottom: 1px solid #44403c;
  }
  .link {
    background: none;
    border: none;
    color: #fbbf24;
    padding: 0;
    font-weight: 600;
    text-align: left;
  }
  .link.current {
    text-decoration: underline;
  }
  .counts {
    color: #a8a29e;
    font-size: 0.8rem;
  }
  .briefing-body {
    background: #0c0a09;
    border: 1px solid #44403c;
    border-radius: 6px;
    padding: 0.9rem 1rem;
    font-size: 0.9rem;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
    color: #fafaf9;
    font-family: "Segoe UI", system-ui, sans-serif;
  }
</style>
