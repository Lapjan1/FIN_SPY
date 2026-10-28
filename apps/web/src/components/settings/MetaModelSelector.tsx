'use client';
import React from 'react';

type Capabilities = {
  max_context: number;
  supports_images: boolean;
  supports_parallel_tools: boolean;
  supports_structured_output: boolean;
  effort_levels: string[];
};

type ModelInfo = {
  id: string;
  provider: string;
  capabilities: Capabilities;
};

const MODELS: ModelInfo[] = [
  {id:'muse-spark-1.1',provider:'freellmapi',capabilities:{max_context:128000,supports_images:true,supports_parallel_tools:true,supports_structured_output:true,effort_levels:['low','medium','high']}},
  {id:'muse-spark-1.3',provider:'meta_official',capabilities:{max_context:1048576,supports_images:true,supports_parallel_tools:true,supports_structured_output:true,effort_levels:['low','medium','high','xhigh']}},
  {id:'muse-wonder-1.0',provider:'meta_official',capabilities:{max_context:1048576,supports_images:true,supports_parallel_tools:true,supports_structured_output:true,effort_levels:['low','medium','high','xhigh']}},
  {id:'muse-image-1.0',provider:'meta_official',capabilities:{max_context:0,supports_images:true,supports_parallel_tools:false,supports_structured_output:false,effort_levels:[]}},
  {id:'sam-3.1',provider:'meta_official',capabilities:{max_context:0,supports_images:true,supports_parallel_tools:false,supports_structured_output:false,effort_levels:[]}},
  {id:'llama3.2:latest',provider:'ollama-local',capabilities:{max_context:131072,supports_images:false,supports_parallel_tools:true,supports_structured_output:true,effort_levels:['low','medium','high']}},
];

export default function MetaModelSelector({ currentModel, effort, onChange }: { currentModel: string; effort: string; onChange: (model:string,effort:string)=>void }) {
  const current = MODELS.find(m=>m.id===currentModel) || MODELS[0];
  return (
    <div className="border border-slate-800 rounded p-4 bg-slate-900 space-y-3">
      <h3 className="font-semibold">Meta Models - Competition Compliant (per docs/SETTINGS.md)</h3>
      <p className="text-xs text-slate-400">FIN_SPY is pure Meta per hackathon rules: Spark series, Wonder, Image, SAM 3.1 via Meta Model API + open-weights Baseten/Modal + Muse Code. Ollama-local only as privacy fallback (local-first).</p>
      
      <div className="flex gap-2 flex-wrap">
        {MODELS.map(m=>(
          <button key={m.id} onClick={()=>onChange(m.id, effort)} className={`px-3 py-1 rounded text-xs border ${currentModel===m.id?'bg-blue-600 border-blue-600':'bg-slate-800 border-slate-700'}`}>
            {m.id} <span className="opacity-60">({m.provider})</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>Max Context: {current.capabilities.max_context.toLocaleString()}</div>
        <div>Images: {current.capabilities.supports_images?'Yes':'No'}</div>
        <div>Parallel Tools: {current.capabilities.supports_parallel_tools?'Yes':'No'}</div>
        <div>Structured Output: {current.capabilities.supports_structured_output?'Yes':'No'}</div>
        <div>Effort Levels: {current.capabilities.effort_levels.join(', ') || 'N/A'}</div>
        <div>Current Effort: 
          <select value={effort} onChange={e=>onChange(currentModel,e.target.value)} className="ml-2 bg-slate-800 border border-slate-700 rounded px-1">
            {current.capabilities.effort_levels.map(l=><option key={l} value={l}>{l}</option>)}
          </select>
        </div>
      </div>

      <div className="text-xs p-2 bg-slate-800 rounded">
        <div>Cost Est: ~$0.045 per 8p statement (2k tokens/page in + 5.5k out) - $150 credit ~3000 statements per homework Part 5.7</div>
        <div>Contributor Warning: muse-spark-1.3-contributor $0.10/$0.20 cheap BUT trains on prompts - NEVER for real bank docs, only synthetic data/samples/ per AGENTS.md</div>
        <div>Privacy Gate: local-first per Flowchart #2 - show_exact_text_before_hosted=true per config/models.yaml</div>
      </div>

      <div className="flex gap-2 text-xs">
        <span className="px-2 py-1 bg-green-900 text-green-300 rounded">freellmapi dev active badge (http://127.0.0.1:3001/v1)</span>
        <span className="px-2 py-1 bg-yellow-900 text-yellow-300 rounded">meta_official pending warning - META_API_KEY expected 1-2 days Cerebral Valley per STATE.md Blocked</span>
      </div>
    </div>
  );
}
