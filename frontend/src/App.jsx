import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Send, Paperclip, X, Plus, Trash2, ToggleLeft, ToggleRight,
  ChevronDown, ChevronRight, Cpu, Zap, Globe, CheckCircle2,
  XCircle, Clock, Loader2, Activity, MessageSquare, Settings,
  Edit2, Save, RefreshCw, Bot, User, AlertCircle, ChevronUp,
  RotateCcw, ShieldCheck, SlidersHorizontal, Wrench, Server,
} from 'lucide-react'

// ─── Shared primitives ────────────────────────────────────────────────────────

const Badge = ({ color = 'default', children }) => {
  const C = {
    default: ['var(--bg-4)', 'var(--text-2)', 'var(--border)'],
    green:   ['var(--green-dim)', 'var(--green)', '#00ff9d30'],
    red:     ['var(--red-dim)', 'var(--red)', '#ff446630'],
    accent:  ['var(--accent-dim)', 'var(--accent)', '#00e5ff30'],
    yellow:  ['#ffd16618', 'var(--yellow)', '#ffd16630'],
  }[color] || ['var(--bg-4)', 'var(--text-2)', 'var(--border)']
  return <span style={{ background: C[0], color: C[1], border: `1px solid ${C[2]}`,
    borderRadius: 4, padding: '2px 7px', fontSize: 11,
    fontFamily: 'var(--font-mono)', fontWeight: 500, letterSpacing: '0.03em' }}>{children}</span>
}

const Dot = ({ color = 'var(--text-3)', pulse }) => (
  <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
    background: color, flexShrink: 0,
    animation: pulse ? 'pulse-dot 1.2s ease-in-out infinite' : 'none' }} />
)

const Spinner = ({ size = 14, color = 'var(--accent)' }) => (
  <Loader2 size={size} color={color} style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />
)

const fmt = s => s ? s.toFixed(2) + 's' : '—'

const PROVIDERS = ['anthropic', 'openai', 'openai_compat', 'local']
const PROVIDER_MODELS = {
  anthropic: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'o1', 'o3-mini'],
  openai_compat: ['custom-model'],
  local: ['llama3', 'mistral', 'codellama', 'phi3'],
}

// ─── Input primitive ──────────────────────────────────────────────────────────
const Inp = ({ label, value, onChange, placeholder, type = 'text', mono = true, small }) => (
  <div style={{ marginBottom: small ? 8 : 12 }}>
    {label && <label style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.07em',
      display: 'block', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>{label.toUpperCase()}</label>}
    <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
      style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)',
        borderRadius: 6, padding: small ? '6px 9px' : '8px 10px', color: 'var(--text)',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-head)', fontSize: small ? 12 : 13,
        outline: 'none', boxSizing: 'border-box' }} />
  </div>
)

const Sel = ({ label, value, onChange, options, small }) => (
  <div style={{ marginBottom: small ? 8 : 12 }}>
    {label && <label style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.07em',
      display: 'block', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>{label.toUpperCase()}</label>}
    <select value={value} onChange={e => onChange(e.target.value)}
      style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)',
        borderRadius: 6, padding: small ? '6px 9px' : '8px 10px', color: 'var(--text)',
        fontFamily: 'var(--font-mono)', fontSize: small ? 12 : 13, outline: 'none' }}>
      {options.map(o => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}
    </select>
  </div>
)

// ─── Agent Form ───────────────────────────────────────────────────────────────
const AgentForm = ({ initial, onSave, onCancel, isEdit }) => {
  const blank = { agent_id: '', provider: 'anthropic', model: 'claude-haiku-4-5-20251001',
    base_url: '', api_key: '', max_tokens: 2048, temperature: 0.7, timeout: 60, max_retries: 3 }
  const [f, setF] = useState(initial || blank)
  const set = (k, v) => setF(p => ({ ...p, [k]: v }))
  const modelOpts = PROVIDER_MODELS[f.provider] || ['custom-model']

  return (
    <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)',
      borderRadius: 10, padding: 16, animation: 'slide-in 0.2s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 13, color: 'var(--accent)' }}>
          {isEdit ? '✎ Edit Agent' : '+ New Agent'}
        </span>
        <button onClick={onCancel} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)' }}>
          <X size={15} />
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 10px' }}>
        <Inp label="Agent ID" value={f.agent_id} onChange={v => set('agent_id', v)} placeholder="my-agent" small />
        <Sel label="Provider" value={f.provider} onChange={v => { set('provider', v); set('model', (PROVIDER_MODELS[v] || [''])[0]) }} options={PROVIDERS} small />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '0 10px', alignItems: 'end' }}>
        <Sel label="Model" value={f.model} onChange={v => set('model', v)} options={modelOpts} small />
        <div style={{ marginBottom: 8 }}>
          <Inp label=" " value={f.model} onChange={v => set('model', v)} placeholder="or type custom" small />
        </div>
      </div>

      <Inp label="API Key" value={f.api_key} onChange={v => set('api_key', v)} placeholder="sk-..." type="password" small />
      {(f.provider === 'openai_compat' || f.provider === 'local') && (
        <Inp label="Base URL" value={f.base_url} onChange={v => set('base_url', v)} placeholder="http://localhost:11434/v1" small />
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 10px' }}>
        <Inp label="Max Tokens" value={String(f.max_tokens)} onChange={v => set('max_tokens', parseInt(v) || 2048)} small />
        <Inp label="Temperature" value={String(f.temperature)} onChange={v => set('temperature', parseFloat(v) || 0.7)} small />
        <Inp label="Timeout (s)" value={String(f.timeout)} onChange={v => set('timeout', parseInt(v) || 60)} small />
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button onClick={onCancel} style={{ flex: 1, padding: '8px', background: 'none',
          border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-2)',
          cursor: 'pointer', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
          Cancel
        </button>
        <button
          onClick={() => { if (f.agent_id && f.provider && f.model) onSave(f) }}
          disabled={!f.agent_id || !f.model}
          style={{ flex: 2, padding: '8px', background: f.agent_id && f.model ? 'var(--accent)' : 'var(--bg-4)',
            color: f.agent_id && f.model ? 'var(--bg)' : 'var(--text-3)',
            border: 'none', borderRadius: 6, cursor: f.agent_id && f.model ? 'pointer' : 'not-allowed',
            fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 12 }}>
          {isEdit ? 'SAVE CHANGES' : 'CREATE AGENT'}
        </button>
      </div>
    </div>
  )
}

// ─── Agents Panel ──────────────────────────────────────────────────────────────
const AgentsPanel = ({ agents, onRefresh }) => {
  const [showForm, setShowForm] = useState(false)
  const [editAgent, setEditAgent] = useState(null)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const handleSave = async (f) => {
    setSaving(true); setErr(null)
    try {
      const method = editAgent ? 'PUT' : 'POST'
      const url = editAgent ? `/agents/${f.agent_id}` : '/agents'
      const res = await fetch(url, {
        method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(f)
      })
      if (!res.ok) {
        const d = await res.json()
        throw new Error(d.detail || 'Failed')
      }
      setShowForm(false); setEditAgent(null)
      await onRefresh()
    } catch (e) { setErr(e.message) }
    setSaving(false)
  }

  const handleDelete = async (id) => {
    if (!confirm(`Delete agent "${id}"?`)) return
    await fetch(`/agents/${id}`, { method: 'DELETE' })
    await onRefresh()
  }

  const providerColor = { anthropic: 'var(--accent)', openai: 'var(--green)', openai_compat: 'var(--yellow)', local: '#c084fc' }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.07em', fontFamily: 'var(--font-mono)' }}>
          WORKER AGENTS ({agents.length})
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={onRefresh} style={{ background: 'none', border: '1px solid var(--border)',
            borderRadius: 5, padding: '4px 8px', cursor: 'pointer', color: 'var(--text-3)', display: 'flex', alignItems: 'center' }}>
            <RefreshCw size={11} />
          </button>
          <button onClick={() => { setShowForm(true); setEditAgent(null) }}
            style={{ display: 'flex', alignItems: 'center', gap: 4,
              background: 'var(--accent-dim)', border: '1px solid #00e5ff30',
              borderRadius: 6, padding: '5px 10px', cursor: 'pointer',
              color: 'var(--accent)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
            <Plus size={11} /> ADD
          </button>
        </div>
      </div>

      {err && <div style={{ background: 'var(--red-dim)', border: '1px solid #ff446630', borderRadius: 6,
        padding: '8px 12px', fontSize: 12, color: 'var(--red)', marginBottom: 10 }}>{err}</div>}

      {(showForm && !editAgent) && (
        <div style={{ marginBottom: 12 }}>
          <AgentForm onSave={handleSave} onCancel={() => setShowForm(false)} />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {agents.map(a => (
          <div key={a.id} style={{ background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 8, overflow: 'hidden' }}>
            {editAgent?.id === a.id
              ? <AgentForm initial={{ ...a, agent_id: a.id }} isEdit onSave={handleSave}
                  onCancel={() => setEditAgent(null)} />
              : <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px' }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                    background: providerColor[a.provider] || 'var(--text-3)' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>
                      {a.id}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <span>{a.provider}</span>
                      <span style={{ color: 'var(--border-2)' }}>·</span>
                      <span style={{ color: 'var(--text-2)' }}>{a.model}</span>
                      {a.base_url && <span style={{ color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 120 }}>{a.base_url}</span>}
                    </div>
                  </div>
                  <button onClick={() => setEditAgent(a)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 4 }}>
                    <Edit2 size={12} />
                  </button>
                  <button onClick={() => handleDelete(a.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 4 }}>
                    <Trash2 size={12} />
                  </button>
                </div>
            }
          </div>
        ))}
        {agents.length === 0 && !showForm && (
          <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-3)', fontSize: 12 }}>
            No agents. Add one to get started.
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Chat Tab ─────────────────────────────────────────────────────────────────
const ChatTab = ({ agents }) => {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState('')
  const [customMode, setCustomMode] = useState(false)
  const [customProvider, setCustomProvider] = useState('anthropic')
  const [customModel, setCustomModel] = useState('claude-haiku-4-5-20251001')
  const [customApiKey, setCustomApiKey] = useState('')
  const [customBaseUrl, setCustomBaseUrl] = useState('')
  const [showConfig, setShowConfig] = useState(false)
  const [systemPrompt, setSystemPrompt] = useState('')
  const bottomRef = useRef()
  const inputRef = useRef()

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => { if (agents.length > 0 && !selectedAgent) setSelectedAgent(agents[0].id) }, [agents])

  const getModelLabel = () => {
    if (customMode) return `${customProvider} / ${customModel}`
    const a = agents.find(x => x.id === selectedAgent)
    return a ? `${a.id} (${a.model})` : 'No agent'
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = { role: 'user', content: input.trim() }
    const history = [...messages, userMsg]
    setMessages(history)
    setInput('')
    setLoading(true)

    try {
      const body = {
        messages: history.map(m => ({ role: m.role, content: m.content })),
        system_prompt: systemPrompt || undefined,
        ...(customMode
          ? { provider: customProvider, model: customModel,
              api_key: customApiKey || undefined, base_url: customBaseUrl || undefined }
          : { agent_id: selectedAgent }),
      }
      const res = await fetch('/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Error')
      setMessages(m => [...m, {
        role: 'assistant', content: data.content,
        meta: { model: data.model, provider: data.provider,
                tokens: data.output_tokens, time: data.duration_seconds }
      }])
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: `**Error:** ${e.message}`, isError: true }])
    }
    setLoading(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const handleKey = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Model selector bar */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-2)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <Bot size={14} color="var(--accent)" />
        <span style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>MODEL:</span>

        <div style={{ display: 'flex', gap: 6, flex: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Agent pills */}
          {!customMode && agents.map(a => (
            <button key={a.id} onClick={() => setSelectedAgent(a.id)}
              style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, cursor: 'pointer',
                fontFamily: 'var(--font-mono)', border: 'none',
                background: selectedAgent === a.id ? 'var(--accent)' : 'var(--bg-3)',
                color: selectedAgent === a.id ? 'var(--bg)' : 'var(--text-2)',
                transition: 'all 0.15s' }}>
              {a.id}
              <span style={{ opacity: 0.6, marginLeft: 4, fontSize: 10 }}>{a.model.split('-').slice(0,2).join('-')}</span>
            </button>
          ))}

          {/* Custom model toggle */}
          <button onClick={() => setCustomMode(m => !m)}
            style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, cursor: 'pointer',
              fontFamily: 'var(--font-mono)', border: `1px solid ${customMode ? 'var(--yellow)' : 'var(--border)'}`,
              background: customMode ? '#ffd16618' : 'none',
              color: customMode ? 'var(--yellow)' : 'var(--text-3)' }}>
            + custom
          </button>
        </div>

        <button onClick={() => setShowConfig(s => !s)}
          style={{ background: 'none', border: 'none', cursor: 'pointer',
            color: showConfig ? 'var(--accent)' : 'var(--text-3)' }}>
          <Settings size={14} />
        </button>

        <button onClick={() => setMessages([])}
          title="Clear chat"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)' }}>
          <Trash2 size={13} />
        </button>
      </div>

      {/* Custom model config panel */}
      {customMode && (
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)',
          background: 'var(--bg-3)', display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: '0 0 130px' }}>
            <Sel label="Provider" value={customProvider} onChange={v => { setCustomProvider(v); setCustomModel((PROVIDER_MODELS[v]||[''])[0]) }} options={PROVIDERS} small />
          </div>
          <div style={{ flex: '1 1 160px' }}>
            <Inp label="Model" value={customModel} onChange={setCustomModel} placeholder="model-name" small />
          </div>
          <div style={{ flex: '1 1 180px' }}>
            <Inp label="API Key" value={customApiKey} onChange={setCustomApiKey} placeholder="sk-..." type="password" small />
          </div>
          {(customProvider === 'openai_compat' || customProvider === 'local') && (
            <div style={{ flex: '1 1 200px' }}>
              <Inp label="Base URL" value={customBaseUrl} onChange={setCustomBaseUrl} placeholder="http://localhost:11434/v1" small />
            </div>
          )}
        </div>
      )}

      {/* System prompt panel */}
      {showConfig && (
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-3)' }}>
          <label style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.07em', display: 'block', marginBottom: 4 }}>
            SYSTEM PROMPT (OPTIONAL)
          </label>
          <textarea value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)}
            placeholder="You are a helpful assistant…"
            style={{ width: '100%', height: 60, resize: 'vertical', background: 'var(--bg)',
              border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px',
              color: 'var(--text)', fontFamily: 'var(--font-mono)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} />
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 60, color: 'var(--text-3)' }}>
            <MessageSquare size={32} style={{ margin: '0 auto 12px', opacity: 0.2 }} />
            <div style={{ fontFamily: 'var(--font-head)', fontSize: 14, color: 'var(--text-2)', marginBottom: 6 }}>
              Direct Chat
            </div>
            <div style={{ fontSize: 12 }}>
              Chat directly with any agent or configure a custom model above.
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 16, animation: 'slide-in 0.2s ease',
            display: 'flex', flexDirection: 'column',
            alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            {/* Label */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4,
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                background: msg.role === 'user' ? 'var(--accent-dim)' : 'var(--bg-4)',
                border: `1px solid ${msg.role === 'user' ? '#00e5ff30' : 'var(--border)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {msg.role === 'user'
                  ? <User size={11} color="var(--accent)" />
                  : <Bot size={11} color="var(--text-3)" />}
              </div>
              <span style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                {msg.role === 'user' ? 'You' : getModelLabel()}
              </span>
              {msg.meta && (
                <span style={{ fontSize: 10, color: 'var(--text-3)' }}>
                  · {msg.meta.tokens} tok · {fmt(msg.meta.time)}
                </span>
              )}
            </div>

            {/* Bubble */}
            <div style={{
              maxWidth: '85%', padding: '10px 14px', borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
              background: msg.role === 'user' ? 'var(--accent-dim)' : msg.isError ? 'var(--red-dim)' : 'var(--bg-2)',
              border: `1px solid ${msg.role === 'user' ? '#00e5ff25' : msg.isError ? '#ff446630' : 'var(--border)'}`,
            }}>
              {msg.role === 'user'
                ? <p style={{ fontSize: 13, color: 'var(--text)', margin: 0, whiteSpace: 'pre-wrap' }}>{msg.content}</p>
                : <div className="md-output" style={{ fontSize: 13 }}><ReactMarkdown>{msg.content}</ReactMarkdown></div>
              }
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
            <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'var(--bg-4)',
              border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Bot size={11} color="var(--text-3)" />
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              {[0,1,2].map(n => <div key={n} style={{ width: 6, height: 6, borderRadius: '50%',
                background: 'var(--text-3)', animation: `pulse-dot 1.2s ${n * 0.2}s infinite` }} />)}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', background: 'var(--bg-2)', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <textarea ref={inputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKey}
            placeholder="Message… (Enter to send, Shift+Enter for newline)"
            rows={1}
            style={{ flex: 1, resize: 'none', background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '9px 12px', color: 'var(--text)',
              fontFamily: 'var(--font-mono)', fontSize: 13, outline: 'none',
              maxHeight: 120, overflowY: 'auto', lineHeight: 1.5 }} />
          <button onClick={sendMessage} disabled={!input.trim() || loading}
            style={{ width: 38, height: 38, borderRadius: 8, flexShrink: 0,
              background: input.trim() && !loading ? 'var(--accent)' : 'var(--bg-4)',
              color: input.trim() && !loading ? 'var(--bg)' : 'var(--text-3)',
              border: 'none', cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
              display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s' }}>
            {loading ? <Spinner size={14} color="var(--text-3)" /> : <Send size={14} />}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Orchestrate result cards ──────────────────────────────────────────────────
const AgentResultCard = ({ response }) => {
  const [open, setOpen] = useState(false)
  const ok = response.status === 'completed'
  const toolTrace = response.metadata?.tool_trace || []
  const toolCount = response.metadata?.tool_calls || 0
  return (
    <div style={{ border: `1px solid ${ok ? '#00ff9d28' : '#ff446628'}`, borderRadius: 8,
      background: ok ? 'var(--green-dim)' : 'var(--red-dim)', overflow: 'hidden', animation: 'slide-in 0.25s ease' }}>
      <button onClick={() => setOpen(o => !o)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text)', textAlign: 'left' }}>
        {ok ? <CheckCircle2 size={14} color="var(--green)" /> : <XCircle size={14} color="var(--red)" />}
        <span style={{ fontFamily: 'var(--font-head)', fontWeight: 600, fontSize: 13 }}>{response.agent_id}</span>
        <Badge color={ok ? 'green' : 'red'}>{response.status}</Badge>
        {toolCount > 0 && <Badge color="accent">🔧 {toolCount} tool{toolCount!==1?'s':''}</Badge>}
        {response.duration_seconds > 0 && <span style={{ color: 'var(--text-3)', fontSize: 11, marginLeft: 'auto', marginRight: 4 }}>{fmt(response.duration_seconds)}</span>}
        {open ? <ChevronUp size={13} color="var(--text-3)" /> : <ChevronDown size={13} color="var(--text-3)" />}
      </button>
      {open && (
        <div style={{ padding: '0 14px 14px', borderTop: '1px solid #ffffff10' }}>
          {toolTrace.length > 0 && (
            <div style={{ margin: '12px 0', background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 6, overflow: 'hidden' }}>
              <div style={{ padding: '6px 10px', background: 'var(--bg-3)', fontSize: 10,
                color: 'var(--accent)', letterSpacing: '0.07em', fontFamily: 'var(--font-mono)' }}>
                TOOL CALLS
              </div>
              {toolTrace.map((t, i) => (
                <div key={i} style={{ padding: '8px 10px', borderTop: i > 0 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontWeight: 600 }}>
                      {t.tool}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                      {JSON.stringify(t.arguments)}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-2)', fontFamily: 'var(--font-mono)',
                    background: 'var(--bg-3)', padding: '4px 8px', borderRadius: 4,
                    maxHeight: 80, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {t.result}
                  </div>
                </div>
              ))}
            </div>
          )}
          {response.error
            ? <p style={{ color: 'var(--red)', fontSize: 13, paddingTop: 12 }}>{response.error}</p>
            : <div className="md-output" style={{ fontSize: 13, paddingTop: 12 }}><ReactMarkdown>{response.result || ''}</ReactMarkdown></div>}
        </div>
      )}
    </div>
  )
}

// ─── Integrations Panel ───────────────────────────────────────────────────────
const IntegrationsPanel = ({ integrations, onAdd, onDelete, onToggle }) => {
  const [showForm, setShowForm] = useState(false)
  const blank = { id:'', name:'', description:'', base_url:'', method:'GET', path_template:'/',
    auth_type:'none', api_key:'', header_name:'Authorization', prefix:'Bearer', param_name:'', param_desc:'' }
  const [f, setF] = useState(blank)
  const set = (k, v) => setF(p => ({ ...p, [k]: v }))

  const handleAdd = async () => {
    if (!f.id || !f.name || !f.base_url) return
    await onAdd({
      id: f.id, name: f.name, description: f.description, base_url: f.base_url,
      method: f.method, path_template: f.path_template,
      auth: f.auth_type !== 'none' ? { type: f.auth_type, api_key: f.api_key, header_name: f.header_name, prefix: f.prefix } : null,
      parameters: f.param_name ? { [f.param_name]: { type: 'string', description: f.param_desc } } : {},
      enabled: true,
    })
    setF(blank); setShowForm(false)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.07em', fontFamily: 'var(--font-mono)' }}>
          API INTEGRATIONS ({integrations.filter(i=>i.enabled).length} active)
        </span>
        <button onClick={() => setShowForm(s => !s)}
          style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--accent-dim)',
            border: '1px solid #00e5ff30', borderRadius: 6, padding: '5px 10px',
            cursor: 'pointer', color: 'var(--accent)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
          <Plus size={11} /> ADD
        </button>
      </div>

      {showForm && (
        <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 10, padding: 14, marginBottom: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 10px' }}>
            <Inp label="ID" value={f.id} onChange={v=>set('id',v)} placeholder="my-api" small />
            <Inp label="Name" value={f.name} onChange={v=>set('name',v)} placeholder="My API" small />
          </div>
          <Inp label="Description" value={f.description} onChange={v=>set('description',v)} placeholder="What it does" small />
          <Inp label="Base URL" value={f.base_url} onChange={v=>set('base_url',v)} placeholder="https://api.example.com" small />
          <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr', gap: '0 10px' }}>
            <Sel label="Method" value={f.method} onChange={v=>set('method',v)} options={['GET','POST','PUT']} small />
            <Inp label="Path Template" value={f.path_template} onChange={v=>set('path_template',v)} placeholder="/search?q={query}" small />
          </div>
          <Sel label="Auth" value={f.auth_type} onChange={v=>set('auth_type',v)} options={['none','api_key','bearer']} small />
          {f.auth_type !== 'none' && <Inp label="API Key" value={f.api_key} onChange={v=>set('api_key',v)} placeholder="key…" type="password" small />}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 10px' }}>
            <Inp label="Param Name" value={f.param_name} onChange={v=>set('param_name',v)} placeholder="query" small />
            <Inp label="Param Desc" value={f.param_desc} onChange={v=>set('param_desc',v)} placeholder="Search query" small />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <button onClick={() => setShowForm(false)} style={{ flex:1, padding:'7px', background:'none', border:'1px solid var(--border)', borderRadius:6, color:'var(--text-2)', cursor:'pointer', fontSize:11 }}>Cancel</button>
            <button onClick={handleAdd} style={{ flex:2, padding:'7px', background:'var(--accent)', color:'var(--bg)', border:'none', borderRadius:6, cursor:'pointer', fontFamily:'var(--font-head)', fontWeight:700, fontSize:11 }}>ADD INTEGRATION</button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {integrations.map(integ => (
          <div key={integ.id} style={{ display: 'flex', alignItems: 'center', gap: 10,
            background: 'var(--bg-2)', border: `1px solid ${integ.enabled ? 'var(--border)' : 'var(--bg-4)'}`,
            borderRadius: 8, padding: '9px 12px', opacity: integ.enabled ? 1 : 0.5, transition: 'opacity 0.2s' }}>
            <Globe size={13} color={integ.enabled ? 'var(--accent)' : 'var(--text-3)'} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-head)', color: 'var(--text)' }}>{integ.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{integ.base_url}</div>
            </div>
            <button onClick={() => onToggle(integ.id, !integ.enabled)} style={{ background:'none', border:'none', cursor:'pointer', color: integ.enabled ? 'var(--green)' : 'var(--text-3)', padding:2 }}>
              {integ.enabled ? <ToggleRight size={17} /> : <ToggleLeft size={17} />}
            </button>
            <button onClick={() => onDelete(integ.id)} style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:2 }}>
              <Trash2 size={12} />
            </button>
          </div>
        ))}
        {integrations.length === 0 && !showForm && (
          <div style={{ textAlign: 'center', color: 'var(--text-3)', fontSize: 12, padding: '16px 0' }}>No integrations</div>
        )}
      </div>
    </div>
  )
}

// ─── Tool Test Panel ──────────────────────────────────────────────────────────
const ToolTestPanel = ({ agents }) => {
  const [agentId, setAgentId] = useState('')
  const [prompt, setPrompt] = useState("What is today's weather in London?")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [err, setErr] = useState(null)

  const run = async () => {
    setLoading(true); setResult(null); setErr(null)
    try {
      const res = await fetch('/debug/tool-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId || undefined, prompt }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setResult(data)
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.07em', marginBottom: 12 }}>LIVE TOOL TEST</div>
      <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.6, marginBottom: 14 }}>
        Verify that tools are actually firing HTTP calls — not just being described to the LLM.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '0 10px' }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>AGENT</div>
          <select value={agentId} onChange={e => setAgentId(e.target.value)}
            style={{ width:'100%', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6,
              padding:'7px 9px', color:'var(--text)', fontFamily:'var(--font-mono)', fontSize:12, outline:'none', marginBottom: 10 }}>
            <option value="">auto-pick</option>
            {agents.map(a => <option key={a.id} value={a.id}>{a.id} ({a.provider})</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>TEST PROMPT</div>
          <input value={prompt} onChange={e => setPrompt(e.target.value)}
            style={{ width:'100%', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6,
              padding:'7px 9px', color:'var(--text)', fontFamily:'var(--font-mono)', fontSize:12, outline:'none',
              marginBottom:10, boxSizing:'border-box' }} />
        </div>
      </div>
      <button onClick={run} disabled={loading}
        style={{ display:'flex', alignItems:'center', gap:7, padding:'8px 16px',
          background: loading ? 'var(--bg-4)' : 'var(--accent)', color: loading ? 'var(--text-3)' : 'var(--bg)',
          border:'none', borderRadius:6, cursor: loading ? 'not-allowed' : 'pointer',
          fontFamily:'var(--font-head)', fontWeight:700, fontSize:12 }}>
        {loading ? <><Spinner size={12} color="var(--text-3)"/> Running…</> : <><Zap size={12}/> Run Tool Test</>}
      </button>
      {err && <div style={{ marginTop:12, background:'var(--red-dim)', border:'1px solid #ff446630', borderRadius:6, padding:'8px 12px', fontSize:12, color:'var(--red)' }}>{err}</div>}
      {result && (
        <div style={{ marginTop:14 }}>
          <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:10 }}>
            <Badge color="accent">{result.agent} · {result.provider}/{result.model}</Badge>
            <Badge color={result.tool_calls_made > 0 ? 'green' : 'red'}>
              {result.tool_calls_made} tool call{result.tool_calls_made!==1?'s':''} made
            </Badge>
            <Badge color="default">tools available: {result.tools_available?.join(', ')}</Badge>
          </div>
          {result.tool_trace?.length > 0 && (
            <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6, marginBottom:10, overflow:'hidden' }}>
              <div style={{ padding:'5px 10px', background:'var(--bg-3)', fontSize:10, color:'var(--accent)', fontFamily:'var(--font-mono)', letterSpacing:'0.07em' }}>TOOL TRACE</div>
              {result.tool_trace.map((t, i) => (
                <div key={i} style={{ padding:'8px 10px', borderTop: i > 0 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', marginBottom:3 }}>
                    {t.tool}({JSON.stringify(t.arguments)})
                  </div>
                  <div style={{ fontSize:11, color:'var(--text-2)', fontFamily:'var(--font-mono)',
                    background:'var(--bg-3)', padding:'4px 8px', borderRadius:4,
                    maxHeight:80, overflow:'auto', whiteSpace:'pre-wrap', wordBreak:'break-all' }}>
                    {t.result}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6, padding:12 }}>
            <div style={{ fontSize:10, color:'var(--text-3)', fontFamily:'var(--font-mono)', marginBottom:6 }}>FINAL ANSWER</div>
            <div className="md-output" style={{ fontSize:13 }}><ReactMarkdown>{result.answer}</ReactMarkdown></div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Settings Panel ───────────────────────────────────────────────────────────
const ROLES = ['researcher','summarizer','analyst','writer','critic','coder','general']

// ─── DocDB Panel ─────────────────────────────────────────────────────────────
const DOCDB_PRESETS = {
  custom: { list_path:'/documents', get_path:'/documents/{id}', id_field:'id', title_field:'title', content_field:'content', list_results_key:'', list_search_param:'q' },
  notion: { list_path:'/v1/databases/{db_id}/query', get_path:'/v1/pages/{id}', id_field:'id', title_field:'properties.Name.title.0.plain_text', content_field:'properties', list_results_key:'results', list_search_param:'', list_method:'POST', get_method:'GET' },
  confluence: { list_path:'/wiki/rest/api/content', get_path:'/wiki/rest/api/content/{id}?expand=body.storage', id_field:'id', title_field:'title', content_field:'body.storage.value', list_results_key:'results', list_search_param:'title' },
  sharepoint: { list_path:"/sites/{site}/drive/root/children", get_path:"/sites/{site}/drive/items/{id}/content", id_field:'id', title_field:'name', content_field:'content', list_results_key:'value', list_search_param:'' },
  elasticsearch: { list_path:'/{index}/_search', get_path:'/{index}/_doc/{id}', id_field:'_id', title_field:'_source.title', content_field:'_source', list_results_key:'hits.hits', list_search_param:'q', list_method:'GET', get_method:'GET' },
  s3_json: { list_path:'/?list-type=2', get_path:'/{id}', id_field:'Key', title_field:'Key', content_field:'', list_results_key:'Contents', list_search_param:'prefix' },
}

const DocDBPanel = () => {
  const [dbs, setDbs] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [testing, setTesting] = useState({})
  const [testResults, setTestResults] = useState({})
  const [expanded, setExpanded] = useState({})
  const blank = {
    id:'', name:'', description:'', base_url:'',
    list_path:'/documents', get_path:'/documents/{id}', search_path:'',
    list_search_param:'q', list_results_key:'', list_method:'GET', get_method:'GET',
    id_field:'id', title_field:'title', summary_field:'', content_field:'content',
    page_size:50, page_size_param:'limit',
    auth_type:'none', api_key:'', header_name:'Authorization', prefix:'Bearer',
    list_body_template:'', get_body_template:'',
  }
  const [f, setF] = useState(blank)
  const set = (k, v) => setF(p => ({...p, [k]: v}))

  const applyPreset = (preset) => {
    const p = DOCDB_PRESETS[preset] || {}
    setF(prev => ({ ...prev, ...p }))
  }

  const load = async () => {
    try { setDbs(await fetch('/docdb').then(r => r.json())) }
    catch {}
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const add = async () => {
    if (!f.id || !f.base_url) return
    const payload = {
      id: f.id, name: f.name || f.id, description: f.description, base_url: f.base_url,
      list_path: f.list_path, get_path: f.get_path,
      search_path: f.search_path || null,
      list_search_param: f.list_search_param || null,
      list_results_key: f.list_results_key,
      list_method: f.list_method, get_method: f.get_method,
      id_field: f.id_field, title_field: f.title_field,
      summary_field: f.summary_field, content_field: f.content_field,
      page_size: Number(f.page_size) || 50,
      page_size_param: f.page_size_param,
      auth: f.auth_type !== 'none' ? { type: f.auth_type, api_key: f.api_key, header_name: f.header_name, prefix: f.prefix } : null,
      list_body_template: f.list_body_template,
      get_body_template: f.get_body_template,
      enabled: true,
    }
    const res = await fetch('/docdb', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
    if (res.ok) { await load(); setF(blank); setShowForm(false) }
    else { const d = await res.json(); alert(d.detail || 'Failed') }
  }

  const remove = async (id) => {
    if (!confirm(`Remove "${id}"?`)) return
    await fetch(`/docdb/${id}`, { method:'DELETE' })
    setDbs(d => d.filter(x => x.id !== id))
  }

  const toggle = async (id, enabled) => {
    await fetch(`/docdb/${id}/toggle?enabled=${enabled}`, { method:'PATCH' })
    setDbs(d => d.map(x => x.id === id ? {...x, enabled} : x))
  }

  const testList = async (id) => {
    setTesting(t => ({...t, [id]: true}))
    try {
      const res = await fetch(`/docdb/${id}/test-list`, { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' })
      const d = await res.json()
      setTestResults(r => ({...r, [id]: { op:'list', text: d.result || d.detail || JSON.stringify(d) }}))
    } catch(e) { setTestResults(r => ({...r, [id]: { op:'list', text: String(e) }})) }
    setTesting(t => ({...t, [id]: false}))
  }

  const testGet = async (id) => {
    const docId = prompt('Enter document ID to fetch:')
    if (!docId) return
    setTesting(t => ({...t, [id+'_get']: true}))
    try {
      const res = await fetch(`/docdb/${id}/test-get`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id: docId}) })
      const d = await res.json()
      setTestResults(r => ({...r, [id]: { op:'get', id: docId, text: d.result || d.detail || JSON.stringify(d) }}))
    } catch(e) { setTestResults(r => ({...r, [id]: { op:'get', text: String(e) }})) }
    setTesting(t => ({...t, [id+'_get']: false}))
  }

  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
        <span style={{ fontSize:11, color:'var(--text-3)', letterSpacing:'0.07em', fontFamily:'var(--font-mono)' }}>
          DOCUMENT DATABASES ({dbs.filter(d=>d.enabled).length} active)
        </span>
        <button onClick={() => setShowForm(s=>!s)}
          style={{ display:'flex', alignItems:'center', gap:4, background:'var(--accent-dim)',
            border:'1px solid #00e5ff30', borderRadius:6, padding:'5px 10px',
            cursor:'pointer', color:'var(--accent)', fontSize:11, fontFamily:'var(--font-mono)' }}>
          <Plus size={11}/> ADD DATABASE
        </button>
      </div>

      {showForm && (
        <div style={{ background:'var(--bg-2)', border:'1px solid var(--border-2)', borderRadius:10, padding:16, marginBottom:14 }}>
          {/* Presets */}
          <div style={{ marginBottom:12 }}>
            <div style={{ fontSize:10, color:'var(--text-3)', marginBottom:6, fontFamily:'var(--font-mono)' }}>QUICK PRESET</div>
            <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
              {Object.keys(DOCDB_PRESETS).map(p => (
                <button key={p} onClick={() => applyPreset(p)}
                  style={{ padding:'3px 9px', background:'var(--bg-4)', border:'1px solid var(--border)',
                    borderRadius:4, cursor:'pointer', fontSize:11, color:'var(--text-2)', fontFamily:'var(--font-mono)' }}>
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 12px' }}>
            <Inp label="Database ID" value={f.id} onChange={v=>set('id',v)} placeholder="my-docs" small />
            <Inp label="Name" value={f.name} onChange={v=>set('name',v)} placeholder="My Document DB" small />
          </div>
          <Inp label="Description (shown to agents)" value={f.description} onChange={v=>set('description',v)} placeholder="Company knowledge base, Q&A articles, etc." small />
          <Inp label="Base URL" value={f.base_url} onChange={v=>set('base_url',v)} placeholder="https://api.example.com" small />

          <div style={{ fontSize:10, color:'var(--text-3)', margin:'10px 0 4px', fontFamily:'var(--font-mono)', letterSpacing:'0.07em' }}>ENDPOINTS</div>
          <div style={{ display:'grid', gridTemplateColumns:'80px 1fr', gap:'0 10px' }}>
            <Sel label="List method" value={f.list_method} onChange={v=>set('list_method',v)} options={['GET','POST']} small />
            <Inp label="List path" value={f.list_path} onChange={v=>set('list_path',v)} placeholder="/documents" small />
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 10px' }}>
            <Inp label="Search param (GET)" value={f.list_search_param} onChange={v=>set('list_search_param',v)} placeholder="q" small />
            <Inp label="Results key (blank=root array)" value={f.list_results_key} onChange={v=>set('list_results_key',v)} placeholder="results" small />
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'80px 1fr', gap:'0 10px' }}>
            <Sel label="Get method" value={f.get_method} onChange={v=>set('get_method',v)} options={['GET','POST']} small />
            <Inp label="Get path (use {id})" value={f.get_path} onChange={v=>set('get_path',v)} placeholder="/documents/{id}" small />
          </div>
          <Inp label="Search path (optional, leave blank to use list+param)" value={f.search_path} onChange={v=>set('search_path',v)} placeholder="/search" small />

          <div style={{ fontSize:10, color:'var(--text-3)', margin:'10px 0 4px', fontFamily:'var(--font-mono)', letterSpacing:'0.07em' }}>FIELD MAPPING</div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:'0 8px' }}>
            <Inp label="ID field" value={f.id_field} onChange={v=>set('id_field',v)} placeholder="id" small />
            <Inp label="Title field" value={f.title_field} onChange={v=>set('title_field',v)} placeholder="title" small />
            <Inp label="Summary field" value={f.summary_field} onChange={v=>set('summary_field',v)} placeholder="summary" small />
            <Inp label="Content field" value={f.content_field} onChange={v=>set('content_field',v)} placeholder="content" small />
          </div>
          <div style={{ fontSize:10, color:'var(--text-3)', marginTop:4, fontFamily:'var(--font-mono)' }}>
            Supports dot-notation for nested fields, e.g. <code style={{color:'var(--accent)'}}>body.storage.value</code>
          </div>

          <div style={{ fontSize:10, color:'var(--text-3)', margin:'10px 0 4px', fontFamily:'var(--font-mono)', letterSpacing:'0.07em' }}>AUTH</div>
          <Sel label="Auth type" value={f.auth_type} onChange={v=>set('auth_type',v)} options={['none','bearer','api_key','basic']} small />
          {f.auth_type !== 'none' && (
            <div style={{ display:'grid', gridTemplateColumns:'1fr 80px 80px', gap:'0 8px' }}>
              <Inp label="API Key / Token" value={f.api_key} onChange={v=>set('api_key',v)} type="password" placeholder="token…" small />
              {f.auth_type === 'api_key' && <>
                <Inp label="Header" value={f.header_name} onChange={v=>set('header_name',v)} placeholder="X-API-Key" small />
                <Inp label="Prefix" value={f.prefix} onChange={v=>set('prefix',v)} placeholder="" small />
              </>}
            </div>
          )}

          <div style={{ display:'flex', gap:8, marginTop:12 }}>
            <button onClick={() => setShowForm(false)}
              style={{ flex:1, padding:'7px', background:'none', border:'1px solid var(--border)', borderRadius:6, color:'var(--text-2)', cursor:'pointer', fontSize:11 }}>Cancel</button>
            <button onClick={add}
              style={{ flex:2, padding:'7px', background:'var(--accent)', color:'var(--bg)', border:'none', borderRadius:6, cursor:'pointer', fontFamily:'var(--font-head)', fontWeight:700, fontSize:12 }}>
              ADD DATABASE
            </button>
          </div>
        </div>
      )}

      {loading && <div style={{ fontSize:12, color:'var(--text-3)', padding:'10px 0' }}>Loading…</div>}

      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        {dbs.map(db => (
          <div key={db.id} style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:8, overflow:'hidden', opacity: db.enabled ? 1 : 0.5 }}>
            <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 12px' }}>
              <Zap size={13} color={db.enabled ? 'var(--accent)' : 'var(--text-3)'} />
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600, fontFamily:'var(--font-head)', color:'var(--text)' }}>{db.name}</div>
                <div style={{ fontSize:10, color:'var(--text-3)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                  {db.base_url} — {db.tools?.join(' · ')}
                </div>
              </div>
              <div style={{ display:'flex', gap:4, alignItems:'center', flexShrink:0 }}>
                <button onClick={() => testList(db.id)} disabled={testing[db.id]}
                  style={{ display:'flex', alignItems:'center', gap:3, padding:'3px 8px',
                    background:'var(--bg-4)', border:'1px solid var(--border)', borderRadius:4,
                    cursor: testing[db.id] ? 'not-allowed' : 'pointer', color:'var(--text-2)', fontSize:10, fontFamily:'var(--font-mono)' }}>
                  {testing[db.id] ? <Spinner size={10}/> : null} list
                </button>
                <button onClick={() => testGet(db.id)} disabled={testing[db.id+'_get']}
                  style={{ display:'flex', alignItems:'center', gap:3, padding:'3px 8px',
                    background:'var(--bg-4)', border:'1px solid var(--border)', borderRadius:4,
                    cursor: testing[db.id+'_get'] ? 'not-allowed' : 'pointer', color:'var(--text-2)', fontSize:10, fontFamily:'var(--font-mono)' }}>
                  {testing[db.id+'_get'] ? <Spinner size={10}/> : null} get
                </button>
                <button onClick={() => toggle(db.id, !db.enabled)}
                  style={{ background:'none', border:'none', cursor:'pointer', color: db.enabled ? 'var(--green)' : 'var(--text-3)', padding:2 }}>
                  {db.enabled ? <ToggleRight size={17}/> : <ToggleLeft size={17}/>}
                </button>
                <button onClick={() => remove(db.id)}
                  style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:2 }}>
                  <Trash2 size={12}/>
                </button>
              </div>
            </div>
            {testResults[db.id] && (
              <div style={{ borderTop:'1px solid var(--border)', padding:'8px 12px' }}>
                <div style={{ fontSize:10, color:'var(--accent)', fontFamily:'var(--font-mono)', marginBottom:4 }}>
                  TEST RESULT — {testResults[db.id].op}{testResults[db.id].id ? ` id=${testResults[db.id].id}` : ''}
                </div>
                <pre style={{ fontSize:11, color:'var(--text-2)', background:'var(--bg)',
                  padding:'6px 8px', borderRadius:4, maxHeight:160, overflow:'auto',
                  whiteSpace:'pre-wrap', wordBreak:'break-all', margin:0 }}>
                  {testResults[db.id].text}
                </pre>
              </div>
            )}
          </div>
        ))}
        {dbs.length === 0 && !loading && !showForm && (
          <div style={{ textAlign:'center', color:'var(--text-3)', fontSize:12, padding:'20px 0' }}>
            No document databases configured.
          </div>
        )}
      </div>
    </div>
  )
}

// ─── MCP Panel ───────────────────────────────────────────────────────────────
const MCPPanel = () => {
  const [servers, setServers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [connecting, setConnecting] = useState({})
  const [expandedTools, setExpandedTools] = useState({})
  const blank = { id:'', name:'', url:'', transport:'sse', api_key:'', description:'' }
  const [f, setF] = useState(blank)
  const set = (k, v) => setF(p => ({...p, [k]: v}))

  const load = async () => {
    try {
      const data = await fetch('/mcp').then(r => r.json())
      setServers(data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const addServer = async () => {
    if (!f.id || !f.url) return
    setConnecting(c => ({...c, [f.id]: true}))
    try {
      const res = await fetch('/mcp', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ...f, auto_connect: true }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setServers(data)
      setF(blank); setShowForm(false)
    } catch(e) { alert(e.message) }
    setConnecting(c => ({...c, [f.id]: false}))
  }

  const reconnect = async (id) => {
    setConnecting(c => ({...c, [id]: true}))
    try {
      const res = await fetch(`/mcp/${id}/connect`, { method:'POST' })
      if (res.ok) await load()
      else { const d = await res.json(); alert(d.detail) }
    } catch(e) { alert(e.message) }
    setConnecting(c => ({...c, [id]: false}))
  }

  const removeServer = async (id) => {
    if (!confirm(`Remove MCP server "${id}"?`)) return
    await fetch(`/mcp/${id}`, { method:'DELETE' })
    setServers(s => s.filter(x => x.id !== id))
  }

  const toggleServer = async (id, enabled) => {
    const res = await fetch(`/mcp/${id}/toggle?enabled=${enabled}`, { method:'PATCH' })
    if (res.ok) await load()
  }

  const providerColor = (connected) => connected ? 'var(--green)' : 'var(--red)'

  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
        <span style={{ fontSize:11, color:'var(--text-3)', letterSpacing:'0.07em', fontFamily:'var(--font-mono)' }}>
          MCP SERVERS ({servers.filter(s=>s.connected).length} connected)
        </span>
        <button onClick={() => setShowForm(s=>!s)}
          style={{ display:'flex', alignItems:'center', gap:4, background:'var(--accent-dim)',
            border:'1px solid #00e5ff30', borderRadius:6, padding:'5px 10px',
            cursor:'pointer', color:'var(--accent)', fontSize:11, fontFamily:'var(--font-mono)' }}>
          <Plus size={11}/> ADD SERVER
        </button>
      </div>

      {showForm && (
        <div style={{ background:'var(--bg-2)', border:'1px solid var(--border-2)', borderRadius:10, padding:14, marginBottom:12 }}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 10px' }}>
            <Inp label="Server ID" value={f.id} onChange={v=>set('id',v)} placeholder="brave-search" small />
            <Inp label="Name" value={f.name} onChange={v=>set('name',v)} placeholder="Brave Search" small />
          </div>
          <Inp label="URL" value={f.url} onChange={v=>set('url',v)} placeholder="https://brave-search.mcp.run/sse" small />
          <div style={{ display:'grid', gridTemplateColumns:'120px 1fr', gap:'0 10px' }}>
            <Sel label="Transport" value={f.transport} onChange={v=>set('transport',v)} options={['sse','http']} small />
            <Inp label="API Key (if required)" value={f.api_key} onChange={v=>set('api_key',v)} placeholder="optional" type="password" small />
          </div>
          <Inp label="Description" value={f.description} onChange={v=>set('description',v)} placeholder="What this server provides" small />
          <div style={{ display:'flex', gap:8, marginTop:4 }}>
            <button onClick={() => setShowForm(false)}
              style={{ flex:1, padding:'7px', background:'none', border:'1px solid var(--border)', borderRadius:6, color:'var(--text-2)', cursor:'pointer', fontSize:11 }}>Cancel</button>
            <button onClick={addServer}
              style={{ flex:2, padding:'7px', background:'var(--accent)', color:'var(--bg)', border:'none', borderRadius:6, cursor:'pointer', fontFamily:'var(--font-head)', fontWeight:700, fontSize:11 }}>
              ADD &amp; CONNECT
            </button>
          </div>
        </div>
      )}

      {loading && <div style={{ fontSize:12, color:'var(--text-3)', padding:'10px 0' }}>Loading…</div>}

      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        {servers.map(srv => (
          <div key={srv.id} style={{ background:'var(--bg-2)', border:`1px solid ${srv.connected ? '#00ff9d22' : 'var(--border)'}`,
            borderRadius:8, overflow:'hidden', opacity: srv.enabled ? 1 : 0.5, transition:'opacity 0.2s' }}>
            {/* Header */}
            <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 12px' }}>
              <div style={{ width:8, height:8, borderRadius:'50%', flexShrink:0, background: providerColor(srv.connected) }} />
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600, fontFamily:'var(--font-head)', color:'var(--text)' }}>{srv.name}</div>
                <div style={{ fontSize:10, color:'var(--text-3)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', fontFamily:'var(--font-mono)' }}>{srv.url}</div>
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:4, flexShrink:0 }}>
                {srv.connected
                  ? <Badge color="green">{srv.tool_count} tool{srv.tool_count!==1?'s':''}</Badge>
                  : <Badge color="red">disconnected</Badge>}
                {!srv.connected && (
                  <button onClick={() => reconnect(srv.id)} disabled={connecting[srv.id]}
                    style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 8px',
                      background:'var(--accent-dim)', border:'1px solid #00e5ff30', borderRadius:4,
                      cursor: connecting[srv.id] ? 'not-allowed' : 'pointer', color:'var(--accent)', fontSize:10, fontFamily:'var(--font-mono)' }}>
                    {connecting[srv.id] ? <Spinner size={10}/> : <RefreshCw size={10}/>} Reconnect
                  </button>
                )}
                <button onClick={() => toggleServer(srv.id, !srv.enabled)}
                  style={{ background:'none', border:'none', cursor:'pointer', color: srv.enabled ? 'var(--green)' : 'var(--text-3)', padding:2 }}>
                  {srv.enabled ? <ToggleRight size={17}/> : <ToggleLeft size={17}/>}
                </button>
                <button onClick={() => removeServer(srv.id)}
                  style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:2 }}>
                  <Trash2 size={12}/>
                </button>
              </div>
            </div>
            {/* Tools list (expandable) */}
            {srv.connected && srv.tool_count > 0 && (
              <div style={{ borderTop:'1px solid var(--border)' }}>
                <button onClick={() => setExpandedTools(e => ({...e, [srv.id]: !e[srv.id]}))}
                  style={{ width:'100%', display:'flex', alignItems:'center', gap:6, padding:'6px 12px',
                    background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', fontSize:11, fontFamily:'var(--font-mono)' }}>
                  {expandedTools[srv.id] ? <ChevronDown size={11}/> : <ChevronRight size={11}/>}
                  TOOLS
                </button>
                {expandedTools[srv.id] && (
                  <div style={{ padding:'0 12px 10px', display:'flex', flexWrap:'wrap', gap:5 }}>
                    {srv.tools.map(t => (
                      <span key={t} style={{ background:'var(--bg-4)', border:'1px solid var(--border)', borderRadius:4,
                        padding:'2px 8px', fontSize:10, color:'var(--accent)', fontFamily:'var(--font-mono)' }}>
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {servers.length === 0 && !loading && !showForm && (
          <div style={{ textAlign:'center', color:'var(--text-3)', fontSize:12, padding:'20px 0' }}>
            No MCP servers. Add one above or set MCP_1_* env vars.
          </div>
        )}
      </div>
    </div>
  )
}

const SettingsPanel = ({ onSaved }) => {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [resetPending, setResetPending] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState(null)
  const [activeSection, setActiveSection] = useState('controller')

  // Local editable copies
  const [ctrl, setCtrl] = useState(null)
  const [prompts, setPrompts] = useState(null)
  const setC = (k, v) => setCtrl(p => ({ ...p, [k]: v }))
  const setP = (k, v) => setPrompts(p => ({ ...p, [k]: v }))
  const setRole = (role, v) => setPrompts(p => ({ ...p, role_prompts: { ...p.role_prompts, [role]: v } }))

  useEffect(() => {
    fetch('/settings').then(r => r.json()).then(d => {
      setSettings(d)
      setCtrl({ ...d.controller, api_key: '' })   // never pre-fill the key field
      setPrompts(d.prompts)
      setLoading(false)
    }).catch(() => { setErr('Could not load settings'); setLoading(false) })
  }, [])

  const saveController = async () => {
    setSaving(true); setErr(null)
    try {
      const res = await fetch('/settings/controller', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ctrl),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
      onSaved && onSaved()
    } catch(e) { setErr(e.message) }
    setSaving(false)
  }

  const savePrompts = async () => {
    setSaving(true); setErr(null)
    try {
      const res = await fetch('/settings/prompts', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prompts),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch(e) { setErr(e.message) }
    setSaving(false)
  }

  const resetPrompts = async () => {
    if (!confirm('Reset all prompts to built-in defaults?')) return
    setResetPending(true)
    try {
      const res = await fetch('/settings/prompts/reset', { method: 'POST' })
      const d = await res.json()
      setPrompts(d)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } catch(e) { setErr(e.message) }
    setResetPending(false)
  }

  if (loading) return <div style={{ padding: 40, textAlign:'center', color:'var(--text-3)' }}><Spinner /></div>

  const sectionBtn = (key, icon, label) => (
    <button onClick={() => setActiveSection(key)}
      style={{ display:'flex', alignItems:'center', gap:8, padding:'8px 12px', borderRadius:6,
        background: activeSection===key ? 'var(--accent-dim)' : 'none',
        border: `1px solid ${activeSection===key ? '#00e5ff22' : 'transparent'}`,
        color: activeSection===key ? 'var(--accent)' : 'var(--text-3)',
        cursor:'pointer', fontSize:12, fontFamily:'var(--font-mono)', width:'100%', textAlign:'left',
        marginBottom:2 }}>
      {icon} {label}
    </button>
  )

  const textArea = (label, value, onChange, rows=4, placeholder='') => (
    <div style={{ marginBottom:14 }}>
      <label style={{ fontSize:10, color:'var(--text-3)', letterSpacing:'0.07em', display:'block', marginBottom:5, fontFamily:'var(--font-mono)' }}>{label.toUpperCase()}</label>
      <textarea value={value} onChange={e=>onChange(e.target.value)} rows={rows} placeholder={placeholder}
        style={{ width:'100%', resize:'vertical', background:'var(--bg)', border:'1px solid var(--border)',
          borderRadius:6, padding:'9px 11px', color:'var(--text)', fontFamily:'var(--font-mono)',
          fontSize:12, lineHeight:1.6, outline:'none', boxSizing:'border-box' }} />
    </div>
  )

  return (
    <div style={{ display:'flex', gap:20, alignItems:'flex-start' }}>
      {/* Section nav */}
      <div style={{ width:160, flexShrink:0 }}>
        <div style={{ fontSize:10, color:'var(--text-3)', letterSpacing:'0.07em', marginBottom:8, fontFamily:'var(--font-mono)' }}>SECTION</div>
        {sectionBtn('controller', <SlidersHorizontal size={12}/>, 'Controller LLM')}
        {sectionBtn('prompts_ctrl', <ShieldCheck size={12}/>, 'Controller Prompts')}
        {sectionBtn('prompts_agent', <Bot size={12}/>, 'Agent Prompts')}
        {sectionBtn('prompts_roles', <Cpu size={12}/>, 'Role Prompts')}
      </div>

      {/* Section content */}
      <div style={{ flex:1, minWidth:0 }}>
        {err && <div style={{ background:'var(--red-dim)', border:'1px solid #ff446630', borderRadius:8,
          padding:'9px 13px', fontSize:12, color:'var(--red)', marginBottom:14 }}>{err}</div>}

        {saved && <div style={{ background:'var(--green-dim)', border:'1px solid #00ff9d30', borderRadius:8,
          padding:'9px 13px', fontSize:12, color:'var(--green)', marginBottom:14, animation:'slide-in 0.2s ease' }}>
          ✓ Settings saved — changes apply on next request
        </div>}

        {/* ── Controller LLM ── */}
        {activeSection === 'controller' && ctrl && (
          <div>
            <div style={{ fontFamily:'var(--font-head)', fontWeight:700, fontSize:15, marginBottom:16 }}>
              Controller LLM
            </div>
            <div style={{ background:'var(--bg-3)', border:'1px solid var(--border)', borderRadius:10, padding:'12px 14px', marginBottom:14, fontSize:12, color:'var(--text-2)', lineHeight:1.6 }}>
              The Controller decomposes user tasks and synthesises final answers. It uses a lower temperature than agents for deterministic task planning.
            </div>

            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 12px' }}>
              <Sel label="Provider" value={ctrl.provider}
                onChange={v => { setC('provider',v); setC('model',(PROVIDER_MODELS[v]||[''])[0]) }}
                options={PROVIDERS} />
              <div>
                <Sel label="Model" value={ctrl.model} onChange={v=>setC('model',v)} options={PROVIDER_MODELS[ctrl.provider]||['custom-model']} />
                <Inp label=" " value={ctrl.model} onChange={v=>setC('model',v)} placeholder="or type custom model" small />
              </div>
            </div>

            <Inp label="API Key (leave blank to keep current)" value={ctrl.api_key||''} onChange={v=>setC('api_key',v)} placeholder="sk-... (only needed to change)" type="password" />
            {(ctrl.provider==='openai_compat'||ctrl.provider==='local') &&
              <Inp label="Base URL" value={ctrl.base_url||''} onChange={v=>setC('base_url',v)} placeholder="http://localhost:11434/v1" />}

            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:'0 10px' }}>
              <Inp label="Max Tokens" value={String(ctrl.max_tokens)} onChange={v=>setC('max_tokens',parseInt(v)||4096)} small />
              <Inp label="Temperature" value={String(ctrl.temperature)} onChange={v=>setC('temperature',parseFloat(v)||0.3)} small />
              <Inp label="Timeout (s)" value={String(ctrl.timeout)} onChange={v=>setC('timeout',parseInt(v)||120)} small />
              <Inp label="Max Retries" value={String(ctrl.max_retries)} onChange={v=>setC('max_retries',parseInt(v)||3)} small />
            </div>

            <button onClick={saveController} disabled={saving}
              style={{ display:'flex', alignItems:'center', gap:7, marginTop:4,
                background: saving ? 'var(--bg-4)' : 'var(--accent)', color: saving ? 'var(--text-3)' : 'var(--bg)',
                border:'none', borderRadius:7, padding:'9px 18px', cursor: saving ? 'not-allowed' : 'pointer',
                fontFamily:'var(--font-head)', fontWeight:700, fontSize:13 }}>
              {saving ? <><Spinner size={13} color="var(--text-3)" /> Saving…</> : <><Save size={13}/> Save Controller</>}
            </button>
          </div>
        )}

        {/* ── Controller Prompts ── */}
        {activeSection === 'prompts_ctrl' && prompts && (
          <div>
            <div style={{ fontFamily:'var(--font-head)', fontWeight:700, fontSize:15, marginBottom:16 }}>
              Controller Prompts
            </div>
            <div style={{ background:'var(--bg-3)', border:'1px solid var(--border)', borderRadius:10, padding:'12px 14px', marginBottom:14, fontSize:12, color:'var(--text-2)', lineHeight:1.6 }}>
              Use <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>{'{agent_descriptions}'}</code> and <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>{'{tools_context}'}</code> in the decompose prompt — they are substituted at runtime.
            </div>
            {textArea('Decompose System Prompt', prompts.decompose_system, v=>setP('decompose_system',v), 10)}
            {textArea('Synthesis System Prompt', prompts.synthesis_system, v=>setP('synthesis_system',v), 5)}
            <div style={{ display:'flex', gap:8 }}>
              <button onClick={resetPrompts} disabled={resetPending}
                style={{ display:'flex', alignItems:'center', gap:6, padding:'8px 14px',
                  background:'none', border:'1px solid var(--border)', borderRadius:7,
                  color:'var(--text-3)', cursor:'pointer', fontSize:12, fontFamily:'var(--font-mono)' }}>
                <RotateCcw size={12}/> Reset All Prompts
              </button>
              <button onClick={savePrompts} disabled={saving}
                style={{ display:'flex', alignItems:'center', gap:7, flex:1,
                  background: saving ? 'var(--bg-4)' : 'var(--accent)', color: saving ? 'var(--text-3)' : 'var(--bg)',
                  border:'none', borderRadius:7, padding:'9px 18px', cursor: saving ? 'not-allowed' : 'pointer',
                  fontFamily:'var(--font-head)', fontWeight:700, fontSize:13 }}>
                {saving ? <><Spinner size={13} color="var(--text-3)"/> Saving…</> : <><Save size={13}/> Save Prompts</>}
              </button>
            </div>
          </div>
        )}

        {/* ── Global Agent Prompt ── */}
        {activeSection === 'prompts_agent' && prompts && (
          <div>
            <div style={{ fontFamily:'var(--font-head)', fontWeight:700, fontSize:15, marginBottom:16 }}>
              Global Agent System Prompt
            </div>
            <div style={{ background:'var(--bg-3)', border:'1px solid var(--border)', borderRadius:10, padding:'12px 14px', marginBottom:14, fontSize:12, color:'var(--text-2)', lineHeight:1.6 }}>
              This text is appended to <em>every</em> agent's system message, after their role persona. Use it to set universal tone, formatting, or behaviour rules across all agents.
            </div>
            {textArea('Global Agent Suffix', prompts.global_agent_system, v=>setP('global_agent_system',v), 6,
              'e.g. Always respond in bullet points. Never use markdown headers.')}
            <button onClick={savePrompts} disabled={saving}
              style={{ display:'flex', alignItems:'center', gap:7,
                background: saving ? 'var(--bg-4)' : 'var(--accent)', color: saving ? 'var(--text-3)' : 'var(--bg)',
                border:'none', borderRadius:7, padding:'9px 18px', cursor: saving ? 'not-allowed' : 'pointer',
                fontFamily:'var(--font-head)', fontWeight:700, fontSize:13 }}>
              {saving ? <><Spinner size={13} color="var(--text-3)"/> Saving…</> : <><Save size={13}/> Save</>}
            </button>
          </div>
        )}

        {/* ── Per-Role Prompts ── */}
        {activeSection === 'prompts_roles' && prompts && (
          <div>
            <div style={{ fontFamily:'var(--font-head)', fontWeight:700, fontSize:15, marginBottom:16 }}>
              Per-Role Prompts
            </div>
            <div style={{ background:'var(--bg-3)', border:'1px solid var(--border)', borderRadius:10, padding:'12px 14px', marginBottom:14, fontSize:12, color:'var(--text-2)', lineHeight:1.6 }}>
              When the controller assigns a role to an agent (researcher, writer, etc.), this persona prompt is prepended to their system message before the global suffix.
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:0 }}>
              {ROLES.map(role => (
                <div key={role} style={{ marginBottom:10 }}>
                  <label style={{ fontSize:10, color:'var(--text-3)', letterSpacing:'0.07em', display:'flex', alignItems:'center', gap:6, marginBottom:4, fontFamily:'var(--font-mono)' }}>
                    <span style={{ background:'var(--bg-4)', border:'1px solid var(--border)', borderRadius:4, padding:'1px 7px', color:'var(--accent)' }}>{role}</span>
                  </label>
                  <textarea value={prompts.role_prompts?.[role]||''} onChange={e=>setRole(role,e.target.value)} rows={2}
                    style={{ width:'100%', resize:'vertical', background:'var(--bg)', border:'1px solid var(--border)',
                      borderRadius:6, padding:'7px 10px', color:'var(--text)', fontFamily:'var(--font-mono)',
                      fontSize:12, lineHeight:1.5, outline:'none', boxSizing:'border-box' }} />
                </div>
              ))}
            </div>
            <div style={{ display:'flex', gap:8, marginTop:4 }}>
              <button onClick={resetPrompts} disabled={resetPending}
                style={{ display:'flex', alignItems:'center', gap:6, padding:'8px 14px',
                  background:'none', border:'1px solid var(--border)', borderRadius:7,
                  color:'var(--text-3)', cursor:'pointer', fontSize:12, fontFamily:'var(--font-mono)' }}>
                <RotateCcw size={12}/> Reset Defaults
              </button>
              <button onClick={savePrompts} disabled={saving}
                style={{ display:'flex', alignItems:'center', gap:7, flex:1,
                  background: saving ? 'var(--bg-4)' : 'var(--accent)', color: saving ? 'var(--text-3)' : 'var(--bg)',
                  border:'none', borderRadius:7, padding:'9px 18px', cursor: saving ? 'not-allowed' : 'pointer',
                  fontFamily:'var(--font-head)', fontWeight:700, fontSize:13 }}>
                {saving ? <><Spinner size={13} color="var(--text-3)"/> Saving…</> : <><Save size={13}/> Save Role Prompts</>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState('orchestrate')
  const [agents, setAgents] = useState([])
  const [integrations, setIntegrations] = useState([])
  const [controller, setController] = useState(null)
  const [mcpInfo, setMcpInfo] = useState({ servers: 0, tools: 0 })
  const [serverOk, setServerOk] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const fileRef = useRef()
  const textRef = useRef()

  // ── Live data via SSE ─────────────────────────────────────────────────────
  useEffect(() => {
    const loadStatic = async () => {
      try {
        const [ag, integ, sett] = await Promise.all([
          fetch('/agents').then(r=>r.json()),
          fetch('/integrations').then(r=>r.json()),
          fetch('/settings').then(r=>r.json()),
        ])
        setAgents(ag.map(a => ({ ...a, id: a.id || a.agent_id })))
        setIntegrations(integ)
        setController(sett.controller)
        setServerOk(true)
      } catch { setServerOk(false) }
    }
    loadStatic()

    // SSE for live agent + controller updates
    const es = new EventSource('/health/stream')
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setAgents(data.agents.map(a => ({ ...a, id: a.id || a.agent_id })))
        if (data.controller) setController(data.controller)
        if (data.mcp_servers !== undefined) setMcpInfo({ servers: data.mcp_servers, tools: data.mcp_tools || 0 })
        setServerOk(true)
      } catch {}
    }
    es.onerror = () => setServerOk(false)
    return () => es.close()
  }, [])

  // ── Auto resize textarea ──────────────────────────────────────────────────
  useEffect(() => {
    if (textRef.current) {
      textRef.current.style.height = 'auto'
      textRef.current.style.height = Math.min(textRef.current.scrollHeight, 180) + 'px'
    }
  }, [prompt])

  const refreshAgents = async () => {
    try {
      const data = await fetch('/agents').then(r => r.json())
      setAgents(data.map(a => ({ ...a, id: a.id || a.agent_id })))
    } catch {}
  }

  const handleSubmit = async () => {
    if (!prompt.trim() || loading) return
    setLoading(true); setResult(null)
    try {
      let res
      if (files.length > 0) {
        const fd = new FormData()
        fd.append('prompt', prompt)
        files.forEach(f => fd.append('files', f))
        res = await fetch('/orchestrate/with-files', { method: 'POST', body: fd })
      } else {
        res = await fetch('/orchestrate', { method: 'POST',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }) })
      }
      setResult(await res.json())
    } catch (e) { setResult({ status: 'failed', error: e.message }) }
    setLoading(false)
  }

  // Integration ops
  const addInteg = async (p) => {
    const res = await fetch('/integrations', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(p) })
    const d = await res.json(); setIntegrations(i => [...i, d])
  }
  const delInteg = async (id) => { await fetch(`/integrations/${id}`, { method:'DELETE' }); setIntegrations(i=>i.filter(x=>x.id!==id)) }
  const toggleInteg = async (id, enabled) => {
    const res = await fetch(`/integrations/${id}/toggle?enabled=${enabled}`, { method:'PATCH' })
    const d = await res.json(); setIntegrations(i => i.map(x => x.id===id ? d : x))
  }

  const TABS = [
    { key: 'orchestrate', icon: <Activity size={13} />, label: 'Orchestrate' },
    { key: 'chat',        icon: <MessageSquare size={13} />, label: 'Chat' },
    { key: 'agents',      icon: <Cpu size={13} />, label: 'Agents' },
    { key: 'docdb',       icon: <Zap size={13} />, label: 'Doc DBs' },
    { key: 'mcp',         icon: <Server size={13} />, label: 'MCP' },
    { key: 'integrations',icon: <Globe size={13} />, label: 'Integrations' },
    { key: 'settings',    icon: <Settings size={13} />, label: 'Settings' },
  ]

  const statusColor = serverOk === null ? 'var(--yellow)' : serverOk ? 'var(--green)' : 'var(--red)'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* ── Sidebar ── */}
      <aside style={{ width: 220, flexShrink: 0, background: 'var(--bg-2)',
        borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
        {/* Logo */}
        <div style={{ padding: '18px 16px 14px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0,
              background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
              display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Activity size={15} color="var(--bg)" />
            </div>
            <div>
              <div style={{ fontFamily: 'var(--font-head)', fontWeight: 800, fontSize: 13, letterSpacing: '-0.01em' }}>
                ORCHESTRATOR
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-3)', letterSpacing: '0.1em' }}>MULTI-AGENT LLM</div>
            </div>
          </div>
          {/* Live status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6,
            background: 'var(--bg-3)', borderRadius: 6, padding: '5px 8px',
            border: '1px solid var(--border)' }}>
            <Dot color={statusColor} pulse={serverOk === null} />
            <span style={{ fontSize: 11, color: 'var(--text-3)', flex: 1 }}>
              {serverOk === null ? 'Connecting…' : serverOk ? 'Online' : 'Offline'}
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-3)' }}>
              {agents.length} agent{agents.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding: '10px 10px 0' }}>
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 10px', borderRadius: 6, marginBottom: 2,
                background: tab === t.key ? 'var(--accent-dim)' : 'none',
                border: `1px solid ${tab === t.key ? '#00e5ff22' : 'transparent'}`,
                color: tab === t.key ? 'var(--accent)' : 'var(--text-3)',
                cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-mono)', textAlign: 'left' }}>
              {t.icon} {t.label}
            </button>
          ))}
        </nav>

        {/* Agent list (live) */}
        <div style={{ padding: '14px 14px 8px', borderTop: '1px solid var(--border)', marginTop: 'auto' }}>
          {controller && (
            <div style={{ marginBottom: 12, paddingBottom: 10, borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.07em', marginBottom: 5 }}>CONTROLLER</div>
              <div style={{ display:'flex', alignItems:'center', gap:7 }}>
                <div style={{ width:6, height:6, borderRadius:'50%', flexShrink:0, background:'var(--yellow)' }} />
                <div>
                  <div style={{ fontSize:11, fontWeight:600, color:'var(--text)', fontFamily:'var(--font-head)' }}>{controller.provider}</div>
                  <div style={{ fontSize:10, color:'var(--text-3)' }}>{controller.model?.split('-').slice(0,3).join('-')}</div>
                </div>
                <button onClick={() => setTab('settings')} title="Edit controller"
                  style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:2, marginLeft:'auto' }}>
                  <Edit2 size={10} />
                </button>
              </div>
            </div>
          )}
          {mcpInfo.servers > 0 && (
            <div style={{ marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.07em', marginBottom: 5 }}>MCP</div>
              <div style={{ display:'flex', alignItems:'center', gap:7 }}>
                <div style={{ width:6, height:6, borderRadius:'50%', flexShrink:0, background:'var(--green)' }} />
                <div>
                  <div style={{ fontSize:11, fontWeight:600, color:'var(--text)', fontFamily:'var(--font-head)' }}>{mcpInfo.servers} server{mcpInfo.servers!==1?'s':''}</div>
                  <div style={{ fontSize:10, color:'var(--text-3)' }}>{mcpInfo.tools} tool{mcpInfo.tools!==1?'s':''} available</div>
                </div>
                <button onClick={() => setTab('mcp')} title="Manage MCP"
                  style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:2, marginLeft:'auto' }}>
                  <Edit2 size={10} />
                </button>
              </div>
            </div>
          )}
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.07em', marginBottom: 8 }}>LIVE AGENTS</div>
          {agents.length === 0
            ? <div style={{ fontSize: 11, color: 'var(--text-3)' }}>No agents</div>
            : agents.slice(0, 4).map(a => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                  background: a.provider === 'anthropic' ? 'var(--accent)' : a.provider === 'openai' ? 'var(--green)' : '#c084fc' }} />
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)', fontFamily: 'var(--font-head)' }}>{a.id}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-3)' }}>{a.model?.split('-').slice(0,3).join('-')}</div>
                </div>
              </div>
            ))
          }
          {agents.length > 4 && <div style={{ fontSize: 10, color: 'var(--text-3)' }}>+{agents.length - 4} more</div>}
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)' }}>
        {/* Top bar */}
        <div style={{ padding: '12px 22px', borderBottom: '1px solid var(--border)',
          background: 'var(--bg-2)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ fontFamily: 'var(--font-head)', fontWeight: 800, fontSize: 15 }}>
            {TABS.find(t => t.key === tab)?.label}
          </span>
          {tab === 'orchestrate' && result && (
            <>
              <Badge color={result.status === 'completed' ? 'green' : 'red'}>{result.status}</Badge>
              {result.total_duration_seconds && (
                <span style={{ fontSize: 11, color: 'var(--text-3)', marginLeft: 'auto' }}>
                  <Clock size={10} style={{ display:'inline', marginRight:4 }} />{fmt(result.total_duration_seconds)}
                </span>
              )}
            </>
          )}
        </div>

        {/* ── Orchestrate Tab ── */}
        {tab === 'orchestrate' && (
          <div style={{ flex: 1, overflow: 'auto', padding: 22 }}>
            <div style={{ maxWidth: 820, margin: '0 auto' }}>
              {/* Input */}
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, overflow:'hidden', marginBottom:20 }}>
                <textarea ref={textRef} value={prompt} onChange={e=>setPrompt(e.target.value)}
                  onKeyDown={e => { if (e.key==='Enter' && (e.metaKey||e.ctrlKey)) handleSubmit() }}
                  placeholder="Describe your task — the controller will decompose it across your agents…"
                  style={{ width:'100%', minHeight:80, resize:'none', background:'none', border:'none',
                    outline:'none', padding:'16px 18px', color:'var(--text)', fontFamily:'var(--font-mono)',
                    fontSize:14, lineHeight:1.6, boxSizing:'border-box' }} />

                {files.length > 0 && (
                  <div style={{ display:'flex', flexWrap:'wrap', gap:6, padding:'0 18px 10px' }}>
                    {files.map((f,i) => (
                      <div key={i} style={{ display:'flex', alignItems:'center', gap:5, background:'var(--bg-4)',
                        border:'1px solid var(--border)', borderRadius:4, padding:'3px 8px' }}>
                        <Paperclip size={10} color="var(--accent)" />
                        <span style={{ fontSize:11, color:'var(--text-2)', maxWidth:150, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{f.name}</span>
                        <button onClick={()=>setFiles(fs=>fs.filter((_,j)=>j!==i))}
                          style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:0, lineHeight:1 }}>
                          <X size={10} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ display:'flex', alignItems:'center', gap:8, padding:'10px 14px',
                  borderTop:'1px solid var(--border)', background:'var(--bg-3)' }}>
                  <input ref={fileRef} type="file" multiple onChange={e=>{ setFiles(f=>[...f,...Array.from(e.target.files||[])]); e.target.value='' }} style={{ display:'none' }} />
                  <button onClick={()=>fileRef.current.click()}
                    style={{ display:'flex', alignItems:'center', gap:5, background:'none',
                      border:'1px solid var(--border)', borderRadius:5, padding:'5px 10px',
                      cursor:'pointer', color:'var(--text-3)', fontSize:12 }}>
                    <Paperclip size={12} /> Attach
                  </button>
                  <div style={{ flex:1 }} />
                  {agents.length === 0 && (
                    <span style={{ fontSize:11, color:'var(--yellow)', display:'flex', alignItems:'center', gap:4 }}>
                      <AlertCircle size={11} /> No agents configured
                    </span>
                  )}
                  <button onClick={handleSubmit} disabled={!prompt.trim()||loading||agents.length===0}
                    style={{ display:'flex', alignItems:'center', gap:7,
                      background: prompt.trim()&&!loading&&agents.length>0 ? 'var(--accent)' : 'var(--bg-4)',
                      color: prompt.trim()&&!loading&&agents.length>0 ? 'var(--bg)' : 'var(--text-3)',
                      border:'none', borderRadius:6, padding:'7px 16px',
                      cursor: prompt.trim()&&!loading&&agents.length>0 ? 'pointer' : 'not-allowed',
                      fontFamily:'var(--font-head)', fontWeight:700, fontSize:13, transition:'all 0.15s' }}>
                    {loading ? <><Spinner size={13} color="var(--text-3)" /> Running</> : <><Send size={13} /> Run <span style={{ opacity:0.5, fontSize:10, fontWeight:400 }}>⌘↵</span></>}
                  </button>
                </div>
              </div>

              {loading && (
                <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12,
                  padding:20, display:'flex', alignItems:'center', gap:14, marginBottom:16 }}>
                  <div style={{ width:36, height:36, borderRadius:'50%', flexShrink:0,
                    border:'2px solid var(--bg-4)', borderTop:'2px solid var(--accent)',
                    animation:'spin 0.8s linear infinite' }} />
                  <div>
                    <div style={{ fontFamily:'var(--font-head)', fontWeight:700, marginBottom:3 }}>Orchestrating…</div>
                    <div style={{ fontSize:12, color:'var(--text-3)' }}>Decomposing task → dispatching {agents.length} agent{agents.length!==1?'s':''} concurrently</div>
                  </div>
                </div>
              )}

              {result && (
                <div style={{ animation:'slide-in 0.3s ease' }}>
                  {result.agent_responses?.length > 0 && (
                    <div style={{ marginBottom:16 }}>
                      <div style={{ fontSize:11, color:'var(--text-3)', letterSpacing:'0.07em', marginBottom:8 }}>
                        AGENT RESULTS — {result.agent_responses.length} AGENT{result.agent_responses.length!==1?'S':''}
                      </div>
                      <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                        {result.agent_responses.map(r => <AgentResultCard key={r.task_id} response={r} />)}
                      </div>
                    </div>
                  )}

                  {result.final_answer && (
                    <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)',
                      borderLeft:'3px solid var(--accent)', borderRadius:12, overflow:'hidden' }}>
                      <div style={{ padding:'12px 18px', borderBottom:'1px solid var(--border)',
                        background:'var(--bg-3)', display:'flex', alignItems:'center', gap:8 }}>
                        <CheckCircle2 size={14} color="var(--accent)" />
                        <span style={{ fontFamily:'var(--font-head)', fontWeight:700, fontSize:13 }}>FINAL ANSWER</span>
                        <span style={{ fontSize:11, color:'var(--text-3)', marginLeft:'auto' }}>{result.sub_task_count} sub-task{result.sub_task_count!==1?'s':''}</span>
                      </div>
                      <div className="md-output" style={{ padding:'18px 20px' }}>
                        <ReactMarkdown>{result.final_answer}</ReactMarkdown>
                      </div>
                    </div>
                  )}

                  {result.error && (
                    <div style={{ background:'var(--red-dim)', border:'1px solid #ff446630', borderRadius:12, padding:16 }}>
                      <div style={{ color:'var(--red)', fontWeight:600, marginBottom:6 }}>Error</div>
                      <div style={{ fontSize:13, color:'var(--text-2)' }}>{result.error}</div>
                    </div>
                  )}
                </div>
              )}

              {!result && !loading && (
                <div style={{ textAlign:'center', padding:'40px 20px', color:'var(--text-3)' }}>
                  <Activity size={32} style={{ margin:'0 auto 12px', opacity:0.2 }} />
                  <div style={{ fontFamily:'var(--font-head)', fontSize:15, marginBottom:6, color:'var(--text-2)' }}>Ready to orchestrate</div>
                  <div style={{ fontSize:12 }}>Type a prompt — the controller decomposes your task<br/>and dispatches sub-tasks to your agents concurrently.</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Chat Tab ── */}
        {tab === 'chat' && (
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <ChatTab agents={agents} />
          </div>
        )}

        {/* ── Agents Tab ── */}
        {tab === 'agents' && (
          <div style={{ flex: 1, overflow: 'auto', padding: 22 }}>
            <div style={{ maxWidth: 680, margin: '0 auto' }}>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20 }}>
                <AgentsPanel agents={agents} onRefresh={refreshAgents} />
              </div>
            </div>
          </div>
        )}

        {/* ── Doc DBs Tab ── */}
        {tab === 'docdb' && (
          <div style={{ flex: 1, overflow: 'auto', padding: 22 }}>
            <div style={{ maxWidth: 680, margin: '0 auto' }}>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20, marginBottom:16 }}>
                <DocDBPanel />
              </div>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20 }}>
                <div style={{ fontSize:11, color:'var(--text-3)', letterSpacing:'0.07em', marginBottom:10 }}>HOW DOCUMENT DATABASES WORK</div>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:'0 0 10px' }}>
                  Each database registers <strong style={{color:'var(--accent)'}}>2–3 tools</strong> the agent uses in sequence:
                </p>
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:8, marginBottom:12 }}>
                  {[
                    ['1. list', 'Discover what docs exist — returns IDs, titles, summaries'],
                    ['2. get', 'Fetch a specific document by ID — returns full content'],
                    ['3. search', 'Optional dedicated search endpoint for semantic/full-text'],
                  ].map(([t,d]) => (
                    <div key={t} style={{ background:'var(--bg-3)', border:'1px solid var(--border)', borderRadius:8, padding:'8px 10px' }}>
                      <div style={{ fontSize:11, color:'var(--accent)', fontFamily:'var(--font-mono)', marginBottom:3 }}>{t}</div>
                      <div style={{ fontSize:11, color:'var(--text-2)', lineHeight:1.5 }}>{d}</div>
                    </div>
                  ))}
                </div>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:'0 0 6px' }}>
                  Use <strong style={{color:'var(--text)'}}>Quick Presets</strong> for common APIs (Confluence, Notion, Elasticsearch, S3). Field mapping supports dot-notation for nested JSON: <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>body.storage.value</code>.
                </p>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:0 }}>
                  Use the <strong style={{color:'var(--text)'}}>list</strong> and <strong style={{color:'var(--text)'}}>get</strong> test buttons inline to verify your field mapping before running a full orchestration.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── MCP Tab ── */}
        {tab === 'mcp' && (
          <div style={{ flex: 1, overflow: 'auto', padding: 22 }}>
            <div style={{ maxWidth: 640, margin: '0 auto' }}>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20, marginBottom:16 }}>
                <MCPPanel />
              </div>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20 }}>
                <div style={{ fontSize:11, color:'var(--text-3)', letterSpacing:'0.07em', marginBottom:10 }}>HOW MCP WORKS</div>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:'0 0 10px' }}>
                  MCP (Model Context Protocol) servers expose tools over SSE or HTTP. Once connected, their tools are automatically available to all agents — no code changes needed.
                </p>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:'0 0 10px' }}>
                  Tools are available under both their bare name (e.g. <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>web_search</code>) and a qualified name (<code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>server-id__web_search</code>) to avoid conflicts.
                </p>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:0 }}>
                  Pre-configure servers with env vars: <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>MCP_1_ID</code>, <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>MCP_1_URL</code>, <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>MCP_1_API_KEY</code>. Use the <strong style={{color:'var(--text)'}}>Integrations → Live Tool Test</strong> to verify they fire.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── Integrations Tab ── */}
        {tab === 'integrations' && (
          <div style={{ flex: 1, overflow: 'auto', padding: 22 }}>
            <div style={{ maxWidth: 600, margin: '0 auto' }}>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20, marginBottom:16 }}>
                <IntegrationsPanel integrations={integrations} onAdd={addInteg} onDelete={delInteg} onToggle={toggleInteg} />
              </div>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20, marginBottom:16 }}>
                <ToolTestPanel agents={agents} />
              </div>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:20 }}>
                <div style={{ fontSize:11, color:'var(--text-3)', letterSpacing:'0.07em', marginBottom:10 }}>HOW TOOL CALLING WORKS</div>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:'0 0 10px' }}>
                  Agents use an <strong style={{color:'var(--accent)'}}>agentic tool loop</strong>: the LLM requests a tool call → your backend executes the real HTTP request → the result is fed back → the LLM uses real data to answer.
                </p>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:'0 0 10px' }}>
                  <strong style={{color:'var(--text)'}}>Anthropic / OpenAI:</strong> native function calling. <strong style={{color:'var(--text)'}}>Ollama / local:</strong> prompt-engineered <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>{'<tool_call>'}</code> blocks — works with any instruction-following model.
                </p>
                <p style={{ fontSize:13, color:'var(--text-2)', lineHeight:1.7, margin:0 }}>
                  Use <code style={{ background:'var(--bg-4)', padding:'1px 5px', borderRadius:3, color:'var(--accent)' }}>{'{param}'}</code> in the path template. The <strong style={{color:'var(--text)'}}>Live Tool Test</strong> above lets you verify HTTP calls are actually firing.
                </p>
              </div>
            </div>
          </div>
        )}
        {/* ── Settings Tab ── */}
        {tab === 'settings' && (
          <div style={{ flex: 1, overflow: 'auto', padding: 22 }}>
            <div style={{ maxWidth: 780, margin: '0 auto' }}>
              <div style={{ background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:12, padding:24 }}>
                <SettingsPanel onSaved={() => {
                  // Refresh controller display after save
                  fetch('/settings').then(r=>r.json()).then(d => setController(d.controller)).catch(()=>{})
                }} />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
