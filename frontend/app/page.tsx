"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { GitHubMark } from "@/components/TopNav";

const proof = [["Intent", "The request says what is changing."], ["Impact", "Dependencies show what else moves."], ["Coverage", "Tests are tied to the PR head."], ["Gate", "Every cited claim is checked."]];
const faqs = [["Does PRism run my code?", "No. PRism reads the pull request diff and related GitHub metadata; it does not execute submitted code."], ["Will it post comments to GitHub?", "No. Repository access is read-only and PRism does not write review comments or modify pull requests."], ["What happens when coverage is missing?", "Coverage remains unknown. PRism does not present a coverage-backed claim without evidence tied to the exact PR head commit."], ["What makes a finding verified?", "The evidence gate confirms its citations against changed lines, dependency facts, or accepted coverage evidence."]];
const demoTranscript = [
  ["00:00", "A code review should do more than summarize a pull request. It should show what changed, why it matters, and the evidence behind each conclusion."],
  ["00:11", "This is PRism, an evidence-backed review workspace that connects intent, impact, coverage, and line-level proof in one place."],
  ["00:22", "Connect GitHub, select a repository and pull request, then start an analysis. PRism checks the change through a series of focused review steps."],
  ["00:34", "As the review runs, each check builds toward a useful answer: what changed, where it could break, and which claims still need verification."],
  ["00:47", "The findings register separates verified issues from unverified claims. Each finding includes severity and supporting evidence, so reviewers can follow the reasoning."],
  ["01:00", "Open the diff to inspect the exact lines behind a finding. Coverage and test evidence show what was exercised, and where confidence is still limited."],
  ["01:12", "Dependency checks can flag assumptions the repository cannot prove, keeping those items visible instead of presenting them as confirmed."],
  ["01:22", "PRism also shows the review method: how facts are collected, how tests run, and how every citation is traced back to the change."],
  ["01:32", "The result is a review someone else can verify, follow, and act on, with the proof kept alongside the conclusion."],
] as const;

export default function HomePage() {
  const { status } = useAuth(); const router = useRouter();
  const [activeProof, setActiveProof] = useState(0);
  const [openFaq, setOpenFaq] = useState(0);
  useEffect(() => { if (status === "signedIn") router.replace("/dashboard"); }, [router, status]);
  if (status === "signedIn") return <p role="status" className="py-20 text-center text-sm text-slate-600">Opening your workspace…</p>;
  return <div className="landing-page" data-testid="public-home">
    <section className="landing-hero">
      <div><p className="landing-label">PRism / Pull request intelligence</p><h1>Proof is the<br /><em>product.</em></h1><p className="landing-lede">A rigorous review surface for changes that move too quickly to trust on instinct. PRism brings intent, impact, coverage, and line-level evidence into one brief.</p><div className="landing-actions"><a href={`${API_URL}/auth/github/login`} className="landing-button"><GitHubMark className="h-4 w-4" /> Connect GitHub</a><a href="#demo" className="landing-link">Watch the demo <span>↓</span></a><Link href="/about" className="landing-link">Read the method <span>→</span></Link></div><p className="landing-note">Read-only access. Your code is never executed or posted back to GitHub.</p></div>
      <div className="landing-proof" aria-label="Synthetic example of review evidence"><div className="proof-top"><span>SYNTHETIC EXAMPLE / REVIEW BRIEF</span><span>PR #248</span></div><div className="proof-content"><div><p className="proof-kicker">Evidence gate</p><h2>Retry can charge an order twice</h2><p className="proof-copy">The retry path calls the gateway before it checks whether the prior attempt completed.</p><div className="proof-code"><span>84</span><code>await gateway.capture(order.total)</code></div></div><aside><p>Claim</p><strong>Changed line</strong><p>Context</p><strong>Call path</strong><p>Verdict</p><b>Verified</b></aside></div><div className="proof-bottom"><span>billing/charge.py:84</span><span>citation matched</span></div></div>
    </section>
    <section id="demo" className="landing-demo" aria-labelledby="landing-demo-heading">
      <div className="landing-demo-heading">
        <div><h2 id="landing-demo-heading">See the review process, end to end.</h2><p>Follow a pull request from GitHub connection through verified findings and cited evidence.</p></div>
        <p className="landing-demo-meta">01:40 <span>·</span> Narrated walkthrough</p>
      </div>
      <figure className="landing-demo-player">
        <video controls playsInline preload="none" poster="/media/prism-demo-poster.jpg" width="1664" height="1080" aria-label="PRism narrated product walkthrough">
          <source src="/media/prism-demo.mp4" type="video/mp4" />
          <track kind="captions" src="/media/prism-demo.en.vtt" srcLang="en" label="English" default />
          Your browser does not support embedded video. <a href="/media/prism-demo.mp4">Open the demo video</a>.
        </video>
      </figure>
      <details className="landing-demo-transcript">
        <summary>Read the transcript</summary>
        <div className="landing-demo-transcript-content">
          {demoTranscript.map(([time, text]) => <p key={time}><time>{time}</time>{text}</p>)}
          <a href="/media/prism-demo-transcript.txt" download>Download transcript</a>
        </div>
      </details>
    </section>
    <section className="landing-manifesto"><p>Good review is not a summary. It is a trail someone else can follow.</p><span>↓</span></section>
    <section id="evidence" className="landing-system"><div><p className="landing-label">A review with a chain of custody</p><h2>Each conclusion has somewhere to stand.</h2></div><div className="system-list">{proof.map(([name, text], index) => <article key={name}><span>0{index + 1}</span><div><h3>{name}</h3><p>{text}</p></div></article>)}</div></section>
    <section id="inspector" className="landing-inspector"><div><p className="landing-label">Try the evidence trail</p><h2>Inspect the reason,<br /><em>not just the result.</em></h2><p>Choose a layer of the review to see the exact kind of evidence it gives a reviewer.</p><div className="inspector-tabs">{proof.map(([name], index) => <button type="button" onClick={() => setActiveProof(index)} aria-pressed={activeProof === index} key={name}>{name}</button>)}</div></div><div className="inspector-screen"><p>Evidence / {proof[activeProof][0]}</p><h3>{proof[activeProof][1]}</h3><div className="inspector-row"><span>source</span><b>{["PR description", "import graph", "coverage artifact", "changed diff line"][activeProof]}</b></div><div className="inspector-row"><span>review state</span><b className="inspector-good">ready for verification</b></div></div></section>
    <section id="workflow" className="landing-workflow"><p className="landing-label">How it works</p><h2>Start with the change. End with a defensible brief.</h2><div>{["Connect your read-only GitHub App", "Select the pull request", "Compute facts before model reasoning", "Inspect verified findings in context"].map((text, index) => <article key={text}><span>0{index + 1}</span><p>{text}</p></article>)}</div></section>
    <section id="compare" className="landing-compare"><div><p className="landing-label">Why PRism</p><h2>A review tool, not a text generator.</h2></div><div role="table"><div role="row" className="compare-head"><span>Capability</span><span>Generic AI summary</span><span>PRism</span></div>{[["Cites changed lines", "Sometimes", "Verified"], ["Connects dependency facts", "Rarely", "Yes"], ["Preserves missing coverage", "Often unclear", "Explicitly unknown"], ["Keeps evidence beside finding", "Usually separate", "Built in"]].map((row) => <div role="row" key={row[0]}><span>{row[0]}</span><span>{row[1]}</span><strong>{row[2]}</strong></div>)}</div></section>
    <section className="landing-split"><div className="split-dark"><p className="landing-label">No false confidence</p><h2>Unknown is a valid answer.</h2><p>When coverage cannot be connected to the exact commit, PRism preserves that uncertainty instead of manufacturing a claim.</p></div><div className="split-paper"><p className="landing-label">A better review handoff</p><h2>Keep the fact beside the finding.</h2><p>Every verified finding includes its file, changed line, and evidence path. The reviewer stays in control.</p><Link href="/about" className="landing-link">Explore the evidence gate <span>→</span></Link></div></section>
    <section id="faq" className="landing-faq"><div><p className="landing-label">The details</p><h2>Questions a serious review tool should answer.</h2></div><div>{faqs.map(([question, answer], index) => <article key={question}><button type="button" aria-expanded={openFaq === index} onClick={() => setOpenFaq(openFaq === index ? -1 : index)}>{question}<span>{openFaq === index ? "−" : "+"}</span></button>{openFaq === index && <p>{answer}</p>}</article>)}</div></section>
    <section className="landing-closing"><p className="landing-label">Built for large and AI-generated changes</p><h2>Review the change.<br /><em>Keep the proof.</em></h2><a href={`${API_URL}/auth/github/login`} className="landing-button"><GitHubMark className="h-4 w-4" /> Start with GitHub</a></section>
  </div>;
}
