"use client";

import Link from "next/link";
import { Dna, ArrowRight, Image as ImageIcon, Zap, BookOpen } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-brand-light text-brand-dark overflow-hidden font-sans selection:bg-brand-primary/30">
      
      {/* Navigation */}
      <nav className="relative z-10 px-8 py-6 flex items-center justify-between max-w-7xl mx-auto fade-in">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center text-brand-dark">
            <Dna className="w-8 h-8" />
          </div>
          <span className="text-xl font-bold tracking-tight text-brand-dark font-serif">BioPath RAG</span>
        </div>
        <Link href="/workbench" className="text-sm font-semibold text-brand-dark hover:text-brand-primary transition-colors">
          Open Workbench
        </Link>
      </nav>

      {/* Hero Section */}
      <main className="relative z-10 max-w-5xl mx-auto px-8 pt-32 pb-20 flex flex-col items-center text-center">
        
        <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-8 slide-up-subtle text-brand-dark" style={{ animationDelay: '0.1s' }}>
          Make sense of <br/>
          <span className="text-brand-dark">complex biology.</span>
        </h1>
        
        <p className="text-lg md:text-xl text-brand-dark/80 max-w-2xl mb-12 slide-up-subtle font-medium leading-relaxed" style={{ animationDelay: '0.2s' }}>
          Reading dozens of clinical trials and deciphering dense pathway diagrams is exhausting. We built BioPath to act as your research partner—helping you find the exact answers you need, without losing your mind in the literature.
        </p>

        <div className="slide-up-subtle flex flex-col sm:flex-row gap-4" style={{ animationDelay: '0.3s' }}>
          <Link href="/workbench" className="group flex items-center justify-center px-8 py-4 font-bold text-brand-light bg-brand-dark rounded-none hover:bg-brand-primary hover:text-brand-dark transition-all focus:outline-none focus:ring-2 focus:ring-brand-primary">
            <span className="flex items-center gap-2">
              Launch Workbench <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </span>
          </Link>
          <a href="#features" className="flex items-center justify-center px-8 py-4 font-bold text-brand-dark bg-transparent border-2 border-brand-dark rounded-none hover:bg-brand-dark hover:text-brand-light transition-colors focus:outline-none focus:ring-2 focus:ring-brand-dark">
            Explore Features
          </a>
        </div>
      </main>

      {/* Features Grid */}
      <section id="features" className="relative z-10 max-w-7xl mx-auto px-8 py-32 border-t border-brand-primary/30">
        <div className="text-center mb-16 slide-up-subtle">
          <h2 className="text-3xl font-bold tracking-tight text-brand-dark mb-4">Like a brilliant colleague, on demand.</h2>
          <p className="text-brand-dark/70">We took care of the heavy lifting so you can focus on the actual science.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 fade-in-staggered">
          {/* Feature 1 */}
          <div className="p-8 bg-white border border-brand-secondary hover:-translate-y-1 hover:shadow-lg transition-all duration-300 group">
            <div className="w-12 h-12 bg-brand-accent text-brand-dark flex items-center justify-center mb-6">
              <BookOpen className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-brand-dark mb-3">Answers you can trust.</h3>
            <p className="text-brand-dark/80 leading-relaxed text-sm">
              Just upload your PDFs and ask away. Every answer comes with an exact page citation, so you never have to guess where the information came from or worry about hallucinations.
            </p>
          </div>

          {/* Feature 2 */}
          <div className="p-8 bg-white border border-brand-secondary hover:-translate-y-1 hover:shadow-lg transition-all duration-300 group">
            <div className="w-12 h-12 bg-brand-accent text-brand-dark flex items-center justify-center mb-6">
              <ImageIcon className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-brand-dark mb-3">It reads diagrams, too.</h3>
            <p className="text-brand-dark/80 leading-relaxed text-sm">
              Biology is highly visual. Whether it's a tangled signaling pathway, a chart, or a chemical structure, just drop the image into the chat—it understands exactly what it's looking at.
            </p>
          </div>

          {/* Feature 3 */}
          <div className="p-8 bg-white border border-brand-secondary hover:-translate-y-1 hover:shadow-lg transition-all duration-300 group">
            <div className="w-12 h-12 bg-brand-accent text-brand-dark flex items-center justify-center mb-6">
              <Zap className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-brand-dark mb-3">Fast and conversational.</h3>
            <p className="text-brand-dark/80 leading-relaxed text-sm">
              No waiting around for a progress bar. Ask a question and watch the insights stream in immediately, allowing you to have a natural, free-flowing conversation with your data.
            </p>
          </div>
        </div>
      </section>
      
      {/* Minimal Footer */}
      <footer className="border-t border-brand-primary/30 py-8 text-center">
        <p className="text-brand-dark/60 text-sm font-medium">© 2026 BioPath RAG. Built for science.</p>
      </footer>
    </div>
  );
}
