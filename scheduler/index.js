// A scheduler tick for the posting workflow. GitHub's own cron fires only a few of its 48
// daily ticks (once on 2026-11-23, so nothing posted for 36 hours); this cron dispatches the
// workflow with tick=true, which runs exactly like a scheduled run: the app posts only a
// planned slot that is due, under the same cap, gap and window.
export default {
  async scheduled(controller, env) {
    if (!env.GH_DISPATCH_TOKEN) {
      throw new Error("GH_DISPATCH_TOKEN is not set: run `npx wrangler secret put GH_DISPATCH_TOKEN`");
    }
    const url = `https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
        "Content-Type": "application/json",
        "User-Agent": "instagram-autopilot-scheduler",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: env.REF, inputs: { tick: "true" } }),
    });
    const when = new Date(controller.scheduledTime).toISOString();
    if (!response.ok) {
      // GitHub's error body names the problem (an expired token reads 401 Bad credentials)
      // and holds no secret; throwing marks this invocation failed in the Worker's logs.
      const detail = (await response.text()).slice(0, 300);
      throw new Error(`dispatch at ${when} failed: HTTP ${response.status} ${detail}`);
    }
    console.log(`dispatched ${env.WORKFLOW} on ${env.REF} for the ${when} tick (${controller.cron})`);
  },
};
