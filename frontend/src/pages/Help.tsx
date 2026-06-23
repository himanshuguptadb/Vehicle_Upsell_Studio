import type { ReactNode } from "react";
import { Card } from "../ui";

// Resolve the app's own URL at runtime so the Help page is correct in any workspace it's
// deployed to (don't hardcode a single workspace's URL).
const APP_URL = typeof window !== "undefined" ? window.location.origin : "";

/** A line the presenter reads out loud (first person). */
function Say({ children }: { children: ReactNode }) {
  return (
    <p className="border-l-4 border-[#FF3621] pl-3 my-2 text-gray-700 italic">{children}</p>
  );
}

/** An action to perform on screen. */
function Do({ children }: { children: ReactNode }) {
  return (
    <p className="flex gap-2 my-1.5 text-sm text-[#1B3139]">
      <span className="text-[#FF3621] font-bold select-none">&rarr;</span>
      <span>{children}</span>
    </p>
  );
}

/** The "what just got easier" payoff line. */
function Win({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 bg-[#1B3139]/5 border border-[#1B3139]/10 rounded-lg px-3 py-2 text-sm text-[#1B3139]">
      💡 <span className="font-medium">What just got easier:</span> {children}
    </p>
  );
}

function Note({ children }: { children: ReactNode }) {
  return <p className="text-xs text-gray-500 mt-3">{children}</p>;
}

export default function HelpPage() {
  return (
    <div>
      <Card>
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded bg-[#FF3621] text-white flex items-center justify-center font-bold shrink-0">🔧</div>
          <div>
            <h1 className="text-xl font-semibold text-[#1B3139]">Vehicle Service Upsell Studio — Demo Run Sheet</h1>
            <p className="text-sm text-gray-600 mt-1">
              ~8–10 min. Read the <span className="italic border-l-4 border-[#FF3621] pl-1">quoted lines</span> out
              loud in first person; <span className="text-[#FF3621] font-bold">&rarr;</span> lines are what you
              <i> do</i> on screen.
            </p>
            <a href={APP_URL} target="_blank" rel="noreferrer" className="text-[#FF3621] text-sm break-all hover:underline">{APP_URL}</a>
          </div>
        </div>
      </Card>

      <Card title="⭐ Before you start (once, 5 min before the audience joins)">
        <p className="text-sm text-gray-600 mb-2">The first AI call is slow while the model “wakes up” — warm these up so it’s instant live:</p>
        <Do>Open the app and let it load (you’ll land on the <b>Components</b> tab — confirm you see Tires, Brake Pads, Battery… If the list is empty, see <i>Troubleshooting</i> below).</Do>
        <Do>Log in with Databricks SSO if prompted.</Do>
        <Do>Go to <b>Prompt Builder</b> → click <b>Generate with AI</b>, then <b>Run test</b> once — wait ~30–60s for the first result. Now the rest of the demo is fast.</Do>
        <Note><b>Tip:</b> the whole demo is the five tabs across the top, left to right: Components → Prompt Builder → Saved Configs → Compare → Deploy.</Note>
      </Card>

      <Card title="PART 1 — The forgotten goldmine (Components tab)">
        <Say>Every time a car comes in for service, the technician writes down detailed measurements — tire tread depth, brake-pad thickness, battery voltage, fluid condition. Then those notes get filed away and forgotten.</Say>
        <Say>Hidden inside them are real safety issues and service opportunities the customer never hears about — and that’s lost revenue and lost trust. Today I’m going to turn those forgotten notes into action, and I’m going to do it without writing a single line of code.</Say>
        <Do>On the <b>Components</b> tab, point to the list of parts. Read part of a rubric out loud, e.g. for Brake Pads: <i>“Urgent: pads under 2mm, grinding, brake warning light.”</i></Do>
        <Say>This is our catalog of what to look for. Each part has a rubric — the criteria for flagging it — and a service manager can edit all of this in plain English. No engineer required.</Say>
        <Do>Click the radio button next to <b>Brake Pads</b>. Point to the bottom: <i>“Selected for analysis: brakes.”</i></Do>
        <Win>the rules live in plain English, owned by the business — not buried in code.</Win>
      </Card>

      <Card title="PART 2 — Build the AI instruction, no code (Prompt Builder tab)">
        <Say>Now I’ll build the actual AI instruction. The old way, this is a ticket to the data team and a two-week wait. Watch how I do it myself in two minutes — I just describe what I want, and the AI drafts it for me.</Say>
        <Do>Click the <b>Prompt Builder</b> tab. Leave <i>“Start from scratch.”</i> Confirm <b>Component = Brake Pads</b>.</Do>
        <Do>In card <b>3 · Prompt</b>, optionally type a hint like <code>prioritize customer safety</code>, then click <b>Generate with AI</b> (✨).</Do>
        <Say>The AI just wrote a full classification prompt for me — in seconds.</Say>
        <Do>(Optional) Type <code>be stricter on tread depth</code> in the hint box and click <b>Improve</b>.</Do>
        <Say>And I keep refining in plain English until it sounds like our shop’s standards.</Say>
        <Do>In card <b>4 · Test on sample data</b>, leave Rows at 10 and click <b>Run test</b> (▶).</Do>
        <p className="my-2 text-sm font-semibold text-[#FF3621]">⭐ This is the moment — slow down here.</p>
        <Do>When results appear, point to the amber banner: <i>“N opportunities the AI surfaced that the technician did NOT flag.”</i></Do>
        <Say>These are real upsell and safety opportunities that were sitting in the notes, missed. That’s revenue we left on the table and a customer we didn’t fully take care of.</Say>
        <Do>Point to the colored bars (Urgent / Upcoming / Good). Scroll the table to an amber row tagged <b>“⚠ AI catch.”</b> Read its technician notes, then the AI’s reasoning column.</Do>
        <Say>The AI read the raw measurements — no verdicts in the notes, just numbers — and explained its call. I’m not rubber-stamping; I can see exactly why.</Say>
        <Do>In card <b>5 · Save config</b>, name it e.g. <code>Brakes – safety first v1</code> and click <b>Save as new config</b> → OK.</Do>
        <Win>a manager builds, tests, and proves an AI policy in minutes — no code, no data-team ticket.</Win>
      </Card>

      <Card title="PART 3 — Pick the best prompt with evidence (Compare tab)">
        <Say>But how do I know my prompt is the right one? I don’t guess — I test two side by side on the exact same cars.</Say>
        <Do>(If you only have one saved config: back on <b>Prompt Builder</b>, type <code>only flag truly urgent</code> → <b>Improve</b> → save as <code>Brakes – conservative v2</code>.)</Do>
        <Do>Click the <b>Compare</b> tab. Set <b>Config A</b> and <b>Config B</b> to your two versions. Click <b>Compare</b>.</Do>
        <Do>Point to the title: <i>“X of Y disagree.”</i> Show the two distribution charts. Tick <i>“disagreements only.”</i></Do>
        <Say>Now I can see exactly where a stricter prompt changes the call — and choose the one that fits our business, with evidence, before it ever touches a real customer.</Say>
        <Win>no more ‘trust me’ — every prompt choice is backed by side-by-side proof.</Win>
      </Card>

      <Card title="PART 4 — Run it across the whole business (Deploy tab)">
        <Say>I’m happy with it. One click runs this across every car in our database and drafts a personalized follow-up email for every customer with an urgent finding.</Say>
        <Do>Click the <b>Deploy</b> tab. Pick your config (e.g. <code>Brakes – safety first v1</code>). Leave <b>“run immediately”</b> checked. Click <b>Deploy job</b>.</Do>
        <Do>When the green <b>“Job created”</b> box appears, click <b>Open job</b> (opens in a new tab).</Do>
        <Say>This is now a scheduled, production job on Databricks — it writes the recommendations and drafts the outreach automatically. What started as a forgotten note is now an email going out to a customer.</Say>
        <Win>from one tested idea to fully automated, business-wide outreach — in one click.</Win>
        <Note>Don’t want to actually kick off a run live? <b>Uncheck “run immediately”</b> before clicking Deploy — it just creates the job.</Note>
      </Card>
    </div>
  );
}
