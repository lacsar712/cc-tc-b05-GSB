<script>
  let session = null;
  let logs = [];
  let loginUser = "surveyor";
  let loginPass = "surv123456";
  let chainage = "";
  let deltaMm = "";
  let error = "";
  let loading = false;
  let timer;
  let route = location.hash === "#/briefings" ? "briefings" : "home";

  let briefings = [];
  let selectedId = null;
  let briefingError = "";
  let briefingBusy = false;

  $: isWriter = session?.role === "writer";
  $: selected = briefings.find((b) => b.id === selectedId) ?? null;

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  function onHashChange() {
    route = location.hash === "#/briefings" ? "briefings" : "home";
  }

  async function refresh() {
    if (!session) return;
    const res = await fetch("/api/logs", { headers: headers() });
    if (res.status === 401) {
      logout();
      return;
    }
    if (res.ok) logs = await res.json();
  }

  async function refreshBriefings(keepSelection = true) {
    if (!session) return;
    const res = await fetch("/api/briefings", { headers: headers() });
    if (res.status === 401) {
      logout();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      briefings = data;
      if (keepSelection && selectedId != null && !data.some((b) => b.id === selectedId)) {
        selectedId = null;
      }
      if (!keepSelection || selectedId == null) {
        selectedId = data.length ? data[0].id : null;
      }
    }
  }

  async function login() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "登录失败";
        return;
      }
      session = { token: data.access_token, username: data.username, role: data.role };
      localStorage.setItem("tunnel_session", JSON.stringify(session));
      await refresh();
      await refreshBriefings(false);
      timer = setInterval(tick, 2000);
    } catch {
      error = "无法连接接口";
    } finally {
      loading = false;
    }
  }

  async function tick() {
    await refresh();
    // 历史清单保持轮询，但已选简报的正文只来自库里冻结的那一份，不随在线数据变
    await refreshBriefings(true);
  }

  function logout() {
    if (timer) clearInterval(timer);
    session = null;
    logs = [];
    briefings = [];
    selectedId = null;
    localStorage.removeItem("tunnel_session");
  }

  async function submit() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({ chainage, delta_mm: Number(deltaMm) }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "提交失败";
        return;
      }
      chainage = "";
      deltaMm = "";
      await refresh();
    } catch {
      error = "提交时网络异常";
    } finally {
      loading = false;
    }
  }

  async function generateBriefing() {
    briefingError = "";
    briefingBusy = true;
    try {
      const res = await fetch("/api/briefings", {
        method: "POST",
        headers: { ...headers() },
      });
      const data = await res.json();
      if (!res.ok) {
        briefingError = data.detail || "生成失败";
        return;
      }
      // 以服务端落库后回传的冻结正文为准，立刻进历史清单并预览这一份
      await refreshBriefings(true);
      selectedId = data.id;
    } catch {
      briefingError = "生成时网络异常";
    } finally {
      briefingBusy = false;
    }
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  }

  const raw = localStorage.getItem("tunnel_session");
  if (raw) {
    try {
      session = JSON.parse(raw);
      refresh();
      refreshBriefings(false);
      timer = setInterval(tick, 2000);
    } catch {
      localStorage.removeItem("tunnel_session");
    }
  }
  window.addEventListener("hashchange", onHashChange);
</script>

<style>
  :global(body) {
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    background: #1c1917;
    color: #f5f5f4;
  }
  main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
  header.top {
    display: flex; align-items: baseline; justify-content: space-between;
    flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.25rem;
  }
  h1 { color: #fbbf24; margin: 0; font-size: 1.35rem; }
  nav { display: flex; gap: 0.5rem; }
  nav a {
    color: #d6d3d1; text-decoration: none; font-size: 0.9rem;
    padding: 0.3rem 0.7rem; border-radius: 6px; border: 1px solid #57534e;
  }
  nav a.active { background: #d97706; color: #fff; border-color: #d97706; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  h2 { font-size: 1rem; margin: 0 0 0.75rem; color: #fde68a; }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  input {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button:disabled { opacity: 0.6; cursor: not-allowed; }
  button.secondary { background: #57534e; }
  .err { color: #fb7185; }
  .hint { color: #a8a29e; font-size: 0.85rem; margin: 0.4rem 0 0; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
  .pending { background: #713f12; color: #fde68a; }
  .layout { display: grid; grid-template-columns: 300px 1fr; gap: 1rem; align-items: start; }
  ul.history { list-style: none; margin: 0; padding: 0; max-height: 420px; overflow-y: auto; }
  ul.history li {
    border: 1px solid #44403c; border-radius: 6px; padding: 0.55rem 0.7rem;
    margin-bottom: 0.5rem; cursor: pointer; background: #0c0a09;
  }
  ul.history li.active { border-color: #d97706; background: #3b2a12; }
  ul.history .meta { font-size: 0.75rem; color: #a8a29e; margin-top: 0.2rem; }
  .chips { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
  .chip { font-size: 0.8rem; padding: 0.15rem 0.55rem; border-radius: 999px; }
  .chip.ok { background: #14532d; color: #86efac; }
  .chip.bad { background: #7f1d1d; color: #fca5a5; }
  .chip.pending { background: #713f12; color: #fde68a; }
  pre.body {
    white-space: pre-wrap; word-break: break-word; background: #0c0a09;
    border: 1px solid #44403c; border-radius: 6px; padding: 0.9rem 1rem;
    margin: 0; font-family: "Segoe UI", system-ui, sans-serif; font-size: 0.9rem;
    line-height: 1.65;
  }
</style>

<main>
  {#if !session}
    <h1>隧道收敛测缝台</h1>
    <p class="sub">测量员提交桩号与收敛毫米值，接口进程内线程认领后出结论。登录框已预填可写账号 surveyor / surv123456。</p>
    <section>
      <label>用户名</label>
      <input bind:value={loginUser} autocomplete="off" />
      <label>密码</label>
      <input type="password" bind:value={loginPass} autocomplete="off" />
      <button disabled={loading} on:click={login}>登录</button>
      {#if error}<p class="err">{error}</p>{/if}
    </section>
  {:else}
    <header class="top">
      <h1>隧道收敛测缝台</h1>
      <nav>
        <a href="#/" class={route === "home" ? "active" : ""}>当班读数</a>
        <a href="#/briefings" class={route === "briefings" ? "active" : ""}>交班签出</a>
      </nav>
    </header>
    <p class="sub">已登录：{session.username}（{isWriter ? "可提交" : "只读"}）</p>
    <section>
      <button class="secondary" on:click={logout}>退出</button>
      <button class="secondary" disabled={loading} on:click={refresh}>刷新列表</button>
    </section>

    {#if route === "home"}
      {#if isWriter}
        <section>
          <label>里程桩号</label>
          <input placeholder="例如 K20+050" bind:value={chainage} />
          <label>收敛（毫米，可正可负）</label>
          <input type="number" step="0.1" bind:value={deltaMm} />
          <button disabled={loading} on:click={submit}>提交（进入待认领）</button>
          {#if error}<p class="err">{error}</p>{/if}
        </section>
      {/if}
      <section>
        <table>
          <thead>
            <tr><th>编号</th><th>桩号</th><th>收敛mm</th><th>状态</th><th>结论</th><th>说明</th></tr>
          </thead>
          <tbody>
            {#each logs as row}
              <tr>
                <td>{row.id}</td>
                <td>{row.chainage}</td>
                <td>{row.delta_mm}</td>
                <td><span class="tag {row.status === 'pending' ? 'pending' : 'ok'}">{row.status === 'pending' ? '待处理' : '已完成'}</span></td>
                <td>
                  {#if row.verdict}
                    <span class="tag {row.verdict === '合格' ? 'ok' : 'bad'}">{row.verdict}</span>
                  {:else}—{/if}
                </td>
                <td>{row.reason ?? "—"}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {:else}
      <section>
        <h2>① 生成交班简报</h2>
        {#if isWriter}
          <button disabled={briefingBusy} on:click={generateBriefing}>
            {briefingBusy ? "正在冻结…" : "按此刻统计生成交班简报"}
          </button>
          <p class="hint">
            按下瞬间由服务端冻结合格 / 超限 / 待判计数与最近几笔提要；生成后在线再变也不改这份正文。
            一张单都没有时也可以生成，计数为 0。
          </p>
        {:else}
          <p class="hint">巡检员只读：可在下方历史清单阅读已生成简报，不能点生成。</p>
        {/if}
        {#if briefingError}<p class="err">{briefingError}</p>{/if}
      </section>

      <div class="layout">
        <section>
          <h2>② 历史清单</h2>
          {#if briefings.length === 0}
            <p class="hint">还没有交班简报。</p>
          {:else}
            <ul class="history">
              {#each briefings as b}
                <li class={b.id === selectedId ? "active" : ""} on:click={() => (selectedId = b.id)}>
                  <div>第 {b.id} 份 · {b.shift_label}</div>
                  <div class="meta">
                    {fmtTime(b.generated_at)} · {b.generated_by} · 共 {b.total_count} 笔
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </section>

        <section>
          <h2>③ 正文预览</h2>
          {#if selected}
            <div class="chips">
              <span class="chip ok">合格 {selected.ok_count}</span>
              <span class="chip bad">超限 {selected.over_count}</span>
              <span class="chip pending">待判 {selected.pending_count}</span>
              <span class="chip" style="background:#44403c;color:#e7e5e4">总计 {selected.total_count}</span>
            </div>
            <pre class="body">{selected.body}</pre>
            <p class="hint">该正文为生成时写库的冻结快照，不可手改。</p>
          {:else}
            <p class="hint">从左侧历史清单选一份简报查看正文。</p>
          {/if}
        </section>
      </div>
    {/if}
  {/if}
</main>
