"use client";

import { useState, useEffect, useRef } from "react";
import { 
  Dna, FileText, CheckCircle2, MessageSquare, 
  Send, Mic, Paperclip, Loader2, Maximize2, Trash2, Upload
} from "lucide-react";
import { cn } from "@/lib/utils";
import { 
  fetchDocuments, uploadDocument, deleteDocument, 
  DocumentMeta, ChatChunk 
} from "@/lib/api";

export default function Home() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<{role: string, content: string, sources?: ChatChunk[]}[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadDocs();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
  }, [chatHistory]);

  const loadDocs = async () => {
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (e) {
      console.error("Failed to load documents", e);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setIsUploading(true);
    try {
      await uploadDocument(file);
      await loadDocs();
    } catch (err) {
      console.error("Upload error:", err);
      alert("Failed to upload document.");
    } finally {
      setIsUploading(false);
      e.target.value = "";
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document?")) return;
    try {
      await deleteDocument(id);
      await loadDocs();
    } catch (e) {
      console.error(e);
      alert("Failed to delete.");
    }
  };

  const handleMicClick = () => {
    if (!('webkitSpeechRecognition' in window)) {
      alert("Speech recognition is not supported in this browser.");
      return;
    }
    const recognition = new (window as any).webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    
    recognition.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setChatInput(prev => prev + (prev ? " " : "") + text);
    };
    recognition.start();
  };

  const handleChat = async () => {
    if (!chatInput.trim() || isTyping) return;

    const userMessage = chatInput;
    setChatInput("");
    setChatHistory(prev => [...prev, { role: "user", content: userMessage }]);
    setIsTyping(true);

    try {
      setChatHistory(prev => [...prev, { role: "assistant", content: "", sources: [] }]);

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMessage, history: [] })
      });

      if (!response.ok) {
        let errorMsg = `Server error: ${response.status} ${response.statusText}`;
        try {
          const errData = await response.json();
          if (errData.detail) errorMsg = errData.detail;
        } catch (e) {}
        throw new Error(errorMsg);
      }

      if (!response.body) throw new Error("No readable stream");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; 

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.replace("data: ", "");
            try {
              const data = JSON.parse(dataStr);
              if (data.type === "token") {
                setChatHistory(prev => {
                  const newHistory = [...prev];
                  const lastIdx = newHistory.length - 1;
                  newHistory[lastIdx] = {
                    ...newHistory[lastIdx],
                    content: newHistory[lastIdx].content + data.content
                  };
                  return newHistory;
                });
              } else if (data.type === "sources") {
                setChatHistory(prev => {
                  const newHistory = [...prev];
                  const lastIdx = newHistory.length - 1;
                  newHistory[lastIdx] = {
                    ...newHistory[lastIdx],
                    sources: data.content
                  };
                  return newHistory;
                });
              } else if (data.type === "done") {
                // stream finished
              }
            } catch (err) {
              console.error("SSE parse error", err, dataStr);
            }
          }
        }
      }
    } catch (err: any) {
      console.error("Chat error:", err);
      setChatHistory(prev => {
        const newHistory = [...prev];
        newHistory[newHistory.length - 1].content = `Error: ${err.message || "Failed to connect to the backend."}`;
        return newHistory;
      });
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-brand-light text-brand-dark font-sans selection:bg-brand-primary/30 selection:text-brand-dark">
      
      {/* ── LEFT PANE: Sidebar (25%) ────────────────────────────── */}
      <aside className="w-[25%] min-w-[300px] bg-brand-light border-r border-brand-primary/30 flex flex-col z-20 fade-in">
        
        {/* Branding */}
        <div className="px-6 py-8 border-b border-brand-primary/30 flex items-center gap-4 bg-brand-light">
          <div className="w-12 h-12 rounded-md bg-brand-dark text-brand-light flex items-center justify-center relative overflow-hidden group">
            <Dna className="w-6 h-6 relative z-10" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-brand-dark font-serif">BioPath RAG</h1>
            <p className="text-[10px] font-bold text-brand-dark/50 uppercase tracking-[0.2em] mt-0.5">Scientific Workbench</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-8 space-y-8">
          
          {/* Upload Section */}
          <section>
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-brand-primary border-dashed rounded-md cursor-pointer bg-white hover:border-brand-dark transition-colors group">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                {isUploading ? (
                  <Loader2 className="w-8 h-8 text-brand-dark animate-spin mb-2" />
                ) : (
                  <Upload className="w-8 h-8 text-brand-primary group-hover:text-brand-dark transition-colors mb-2" />
                )}
                <p className="text-sm font-semibold text-brand-dark">
                  {isUploading ? "Indexing document..." : "Upload PDF or Image"}
                </p>
                <p className="text-xs text-brand-dark/50 mt-1">Drag & drop or click to browse</p>
              </div>
              <input type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg" onChange={handleFileUpload} disabled={isUploading} />
            </label>
          </section>

          {/* Document List */}
          <section>
            <h2 className="text-[10px] font-bold text-brand-dark/60 uppercase tracking-[0.15em] mb-4 flex items-center gap-2">
              <span className="w-4 h-px bg-brand-primary/50" />
              Indexed Documents ({documents.length})
            </h2>
            <div className="space-y-3">
              {documents.length === 0 ? (
                <div className="text-sm text-brand-dark/50 text-center py-6">No documents indexed yet.</div>
              ) : documents.map((doc) => (
                <div key={doc.id} className="p-4 rounded-md border border-brand-primary/30 bg-white flex items-start justify-between group hover:-translate-y-[1px] transition-transform">
                  <div className="flex items-start gap-3 overflow-hidden">
                    <div className="p-2 rounded-md bg-brand-accent text-brand-dark shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="truncate">
                      <p className="text-sm font-semibold text-brand-dark truncate" title={doc.name}>{doc.name}</p>
                      <p className="text-[11px] text-brand-dark/60 mt-1 font-medium">
                        {doc.pages} pages • {doc.images} images
                      </p>
                    </div>
                  </div>
                  <button onClick={() => handleDelete(doc.id)} className="p-2 text-brand-dark/40 hover:text-brand-dark hover:bg-brand-primary/20 rounded-sm transition-colors opacity-0 group-hover:opacity-100">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>
      </aside>

      {/* ── MAIN PANE: Conversational RAG (75%) ──────────────────────── */}
      <main className="w-[75%] flex flex-col bg-white relative z-10">
        
        {/* Header */}
        <div className="px-10 py-6 border-b border-brand-primary/30 flex items-center justify-between bg-white shrink-0 z-20">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-md bg-brand-dark flex items-center justify-center text-brand-light">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-brand-dark tracking-tight">AI Research Assistant</h2>
              <p className="text-[11px] text-brand-dark/60 font-bold uppercase tracking-widest flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-primary animate-pulse" />
                Multimodal Engine Active
              </p>
            </div>
          </div>
        </div>

        {/* Chat Feed */}
        <div className="flex-1 overflow-y-auto px-10 py-10 space-y-8 relative">
          
          <div className="max-w-4xl mx-auto space-y-8 relative z-10">
            {chatHistory.length === 0 && (
              <div className="text-center py-20 text-brand-dark/60 fade-in">
                <div className="w-16 h-16 bg-brand-light rounded-full flex items-center justify-center mx-auto mb-4 border border-brand-primary/30">
                  <Dna className="w-8 h-8 text-brand-primary" />
                </div>
                <h3 className="text-lg font-semibold text-brand-dark">Start your research</h3>
                <p className="text-sm mt-2 max-w-sm mx-auto">Ask questions about your uploaded biological papers, signaling pathways, or clinical trials.</p>
              </div>
            )}

            {chatHistory.map((msg, idx) => (
              <div key={idx} className={cn("flex gap-5 slide-up-subtle", msg.role === "user" ? "flex-row-reverse" : "")}>
                <div className={cn(
                  "w-10 h-10 rounded-md flex items-center justify-center shrink-0 border border-transparent font-bold text-sm",
                  msg.role === "user" 
                    ? "bg-brand-primary text-brand-dark" 
                    : "bg-brand-dark text-brand-light"
                )}>
                  {msg.role === "user" ? "U" : <Dna className="w-5 h-5" />}
                </div>
                
                <div className="flex flex-col gap-3 max-w-[85%]">
                  <div className={cn(
                    "px-6 py-4 text-[15px] leading-relaxed rounded-md",
                    msg.role === "user" 
                      ? "bg-brand-primary text-brand-dark" 
                      : "text-brand-dark bg-transparent"
                  )}>
                    {msg.content}
                    {msg.role === "assistant" && !msg.content && isTyping && (
                      <span className="flex gap-1 items-center h-6 text-brand-primary">
                        <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce" />
                        <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce delay-100" />
                        <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce delay-200" />
                      </span>
                    )}
                  </div>

                  {/* Sources & Images rendered by Assistant */}
                  {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-4 mt-2">
                      {msg.sources.map((src, i) => (
                        <div key={i} className="bg-white border border-brand-primary/30 p-3 rounded-md hover:border-brand-primary hover:-translate-y-[1px] transition-all max-w-[280px]">
                          {src.modality === "image" && src.image_path && (
                            <div className="mb-2 rounded-sm overflow-hidden border border-brand-primary/30 cursor-pointer relative group"
                                 onClick={() => setSelectedImage(`/images/${src.image_path?.split(/[\\/]/).pop()}`)}>
                              <img src={`/images/${src.image_path.split(/[\\/]/).pop()}`} alt="Source figure" className="w-full h-32 object-cover" />
                              <div className="absolute inset-0 bg-brand-dark/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                <Maximize2 className="w-5 h-5 text-white" />
                              </div>
                            </div>
                          )}
                          <div className="flex items-start gap-2">
                            <CheckCircle2 className="w-3.5 h-3.5 text-brand-primary mt-0.5 shrink-0" />
                            <div className="text-[11px] text-brand-dark/80 leading-relaxed font-medium">
                              {src.text}
                            </div>
                          </div>
                          <div className="mt-2 text-[9px] font-bold text-brand-dark/50 uppercase tracking-wider px-1">
                            {src.source_pdf} • Page {src.page_number}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} className="h-4" />
          </div>
        </div>

        {/* Composer */}
        <div className="p-4 bg-brand-light border-t border-brand-primary/30 shrink-0 z-20">
          <div className="max-w-4xl mx-auto">
            <div className="bg-white border border-brand-primary/50 rounded-md focus-within:border-brand-dark focus-within:ring-1 focus-within:ring-brand-dark transition-all duration-300 overflow-hidden shadow-sm">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleChat();
                  }
                }}
                placeholder="Ask about pathways, mutations, or analyze specific figures..."
                className="w-full bg-transparent px-4 py-3 text-[14px] text-brand-dark placeholder:text-brand-dark/40 focus:outline-none resize-none h-[50px]"
              />
              <div className="flex items-center justify-between px-4 pb-2 border-t border-brand-primary/10 pt-2">
                <div className="flex items-center gap-2">
                  <label className="p-2 text-brand-dark/60 hover:text-brand-dark hover:bg-brand-light rounded-sm transition-colors cursor-pointer group relative">
                    <Paperclip className="w-4 h-4" />
                    <input type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg" onChange={handleFileUpload} disabled={isUploading} />
                  </label>
                  <button 
                    onClick={handleMicClick}
                    className={cn(
                      "p-2 rounded-sm transition-colors",
                      isListening ? "text-brand-dark bg-brand-secondary animate-pulse" : "text-brand-dark/60 hover:text-brand-dark hover:bg-brand-light"
                    )}
                  >
                    <Mic className="w-4 h-4" />
                  </button>
                </div>
                <button 
                  onClick={handleChat}
                  disabled={!chatInput.trim() || isTyping}
                  className={cn(
                    "flex items-center gap-2 px-6 py-2 rounded-sm font-bold text-sm transition-all duration-300",
                    chatInput.trim() && !isTyping
                      ? "bg-brand-dark text-brand-light hover:bg-brand-dark/90 hover:-translate-y-0.5" 
                      : "bg-brand-light text-brand-dark/40 border border-brand-primary/30 cursor-not-allowed"
                  )}
                >
                  <span>Analyze</span>
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Image Modal */}
      {selectedImage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-10 bg-brand-dark/80" onClick={() => setSelectedImage(null)}>
          <div className="bg-brand-light rounded-md p-2 max-w-5xl max-h-full overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-end p-2 mb-2">
              <button onClick={() => setSelectedImage(null)} className="p-2 text-brand-dark/60 hover:bg-brand-primary/20 rounded-sm">Close</button>
            </div>
            <img src={selectedImage} alt="Enlarged" className="w-full h-auto rounded-sm" />
          </div>
        </div>
      )}

    </div>
  );
}
