import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Send, Paperclip, X, Plus, Trash2, ToggleLeft, ToggleRight,
  ChevronDown, ChevronRight, Cpu, Zap, Globe, Settings,
  CheckCircle2, XCircle, Clock, Loader2, Activity, Key, Link
} from 'lucide-react'

const API = ''  // same-origin when served by FastAPI

// ─── Utilities ────────────────────────────────────────────────────────────────
const cls = (...args) => args.filter(Boolean).join(' ')
const fmt = (s) => s ? s.toFixed(2) + 's' : '—'

// ─── Tiny styled primitives ───────────────────────────────────────────────────
const Badge = ({ color = 'default', children }) => {
  const colors = {
    default: { bg: 'var(--bg-4)', color: 'var(--text-2)', border: 'var(--border)' },
    green:   { bg: 'var(--green-dim)', color: 'var(--green)', border: '#00ff9d30' },
    red:     { bg: 'var(--red-dim)', color: 'var(--red)', border: '#ff446630' },
    accent:  { bg: 'var(--accent-dim)', color: 'var(--accent)', border: '#00e5ff30' },
    yellow:  { bg: '#ffd16618', color: 'var(--yellow)', border: '#ffd16630' },
  }
  const c = colors[color] || colors.default
  return (
    <span style={{
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
      borderRadius: 4, padding: '2px 7px', fontSize: 11,
      fontFamily: 'var(--font-mono)', fontWeight: 500, letterSpacing: '0.03em',
    }}>{children}</span>
  )
}

const Dot = ({ color = 'var(--text-3)', pulse }) => (
  <span style={{
    display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
    background: color, flexShrink: 0,
    animation: pulse ? 'pulse-dot 1.2s ease-in-out infinite' : 'none',
  }} />
)

// ─── Agent Card ───────────────────────────────────────────────────────────────
const AgentCard = ({ response, isRunning }) => {
  const [open, setOpen] = useState(false)
  const ok = response.status === 'completed'
  const failed = response.status === 'failed'

  return (
    <div style={{
      border: `1px solid ${ok ? '#00ff9d28' : failed ? '#ff446628' : 'var(--border)'}`,
      borderRadius: var => 'var(--radius)',
      background: ok ? 'var(--green-dim)' : failed ? 'var(--red-dim)' : 'var(--bg-3)',
      overflow: 'hidden',
      animation: 'slide-in 0.25s ease',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 14px', background: 'none', border: 'none',
          cursor: 'pointer', color: 'var(--text)', textAlign: 'left',
        }}
      >
        {isRunning
          ? <Loader2 size={14} color="var(--accent)" style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />
          : ok
            ? <CheckCircle2 size={14} color="var(--green)" style={{ flexShrink: 0 }} />
            : <XCircle size={14} color="var(--red)" style={{ flexShrink: 0 }} />
        }
        <span style={{ fontFamily: 'var(--font-head)', fontWeight: 600, fontSize: 13 }}>
          {response.agent_id}
        </span>
        <Badge color={ok ? 'green' : failed ? 'red' : 'accent'}>
          {response.status}
        </Badge>
        {response.duration_seconds > 0 && (
          <span style={{ color: 'var(--text-3)', fontSize: 11, marginLeft: 'auto', marginRight: 4 }}>
            {fmt(response.duration_seconds)}
          </span>
        )}
        {response.token_usage?.output > 0 && (
          <span style={{ color: 'var(--text-3)', fontSize: 11 }}>
            {response.token_usage.output} tok
          </span>
        )}
        {open
          ? <ChevronDown size={13} color="var(--text-3)" />
          : <ChevronRight size={13} color="var(--text-3)" />
        }
      </button>
      {open && (
        <div style={{ padding: '0 14px 14px', borderTop: '1px solid var(--border)' }}>
          <div style={{ paddingTop: 12 }}>
            {response.error
              ? <p style={{ color: 'var(--red)', fontSize: 13 }}>{response.error}</p>
              : <div className="md-output" style={{ fontSize: 13 }}>
                  <ReactMarkdown>{response.result || ''}</ReactMarkdown>
                </div>
            }
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Integration Form ─────────────────────────────────────────────────────────
const IntegrationForm = ({ onAdd, onClose }) => {
  const [form, setForm] = useState({
    id: '', name: '', description: '', base_url: '',
    method: 'GET', path_template: '/', auth_type: 'none',
    api_key: '', header_name: 'Authorization', prefix: 'Bearer',
    param_name: '', param_desc: '',
  })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = () => {
    if (!form.id || !form.name || !form.base_url) return
    const payload = {
      id: form.id, name: form.name,
      description: form.description, base_url: form.base_url,
      method: form.method, path_template: form.path_template,
      auth: form.auth_type !== 'none' ? {
        type: form.auth_type,
        api_key: form.api_key,
        header_name: form.header_name,
        prefix: form.prefix,
      } : null,
      parameters: form.param_name
        ? { [form.param_name]: { type: 'string', description: form.param_desc } }
        : {},
      enabled: true,
    }
    onAdd(payload)
  }

  const inp = {
    background: 'var(--bg-2)', border: '1px solid var(--border)',
    borderRadius: 6, padding: '8px 10px', color: 'var(--text)',
    fontFamily: 'var(--font-mono)', fontSize: 13, width: '100%',
    outline: 'none',
  }
  const lbl = { fontSize: 11, color: 'var(--text-3)', marginBottom: 4, display: 'block', letterSpacing: '0.05em' }
  const field = (label, key, placeholder, opts = {}) => (
    <div style={{ marginBottom: 12 }}>
      <label style={lbl}>{label.toUpperCase()}</label>
      {opts.type === 'select'
        ? <select value={form[key]} onChange={e => set(key, e.target.value)} style={inp}>
            {opts.options.map(o => <option key={o}>{o}</option>)}
          </select>
        : <input
            style={inp} placeholder={placeholder}
            value={form[key]} onChange={e => set(key, e.target.value)}
          />
      }
    </div>
  )

  return (
    <div style={{
      background: 'var(--bg-2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: 20,
      animation: 'slide-in 0.2s ease',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 14 }}>Add Integration</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)' }}>
          <X size={16} />
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
        <div>{field('ID', 'id', 'my-api')}</div>
        <div>{field('Name', 'name', 'My API')}</div>
      </div>
      {field('Description (shown to agents)', 'description', 'What does this API do?')}
      {field('Base URL', 'base_url', 'https://api.example.com')}
      <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr', gap: '0 12px' }}>
        <div>{field('Method', 'method', '', { type: 'select', options: ['GET', 'POST', 'PUT'] })}</div>
        <div>{field('Path Template', 'path_template', '/search?q={query}')}</div>
      </div>
      {field('Auth Type', 'auth_type', '', { type: 'select', options: ['none', 'api_key', 'bearer'] })}
      {form.auth_type !== 'none' && (
        <>
          {field('API Key', 'api_key', 'sk-...')}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px', gap: '0 12px' }}>
            <div>{field('Header Name', 'header_name', 'Authorization')}</div>
            <div>{field('Prefix', 'prefix', 'Bearer')}</div>
          </div>
        </>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
        <div>{field('Parameter Name', 'param_name', 'query')}</div>
        <div>{field('Parameter Description', 'param_desc', 'Search query')}</div>
      </div>
      <button
        onClick={handleSubmit}
        style={{
          width: '100%', padding: '10px', marginTop: 4,
          background: 'var(--accent)', color: 'var(--bg)', border: 'none',
          borderRadius: 6, cursor: 'pointer', fontFamily: 'var(--font-head)',
          fontWeight: 700, fontSize: 13, letterSpacing: '0.03em',
        }}
      >
        ADD INTEGRATION
      </button>
    </div>
  )
}

// ─── Integrations Panel ───────────────────────────────────────────────────────
const IntegrationsPanel = ({ integrations, onAdd, onDelete, onToggle }) => {
  const [showForm, setShowForm] = useState(false)

  const handleAdd = async (payload) => {
    await onAdd(payload)
    setShowForm(false)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 13, letterSpacing: '0.05em', color: 'var(--text-2)' }}>
          API INTEGRATIONS
        </span>
        <button
          onClick={() => setShowForm(s => !s)}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            background: 'var(--accent-dim)', border: '1px solid #00e5ff30',
            borderRadius: 6, padding: '5px 10px', cursor: 'pointer',
            color: 'var(--accent)', fontSize: 12, fontFamily: 'var(--font-mono)',
          }}
        >
          <Plus size={12} /> ADD
        </button>
      </div>

      {showForm && <IntegrationForm onAdd={handleAdd} onClose={() => setShowForm(false)} />}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: showForm ? 12 : 0 }}>
        {integrations.map(integ => (
          <div key={integ.id} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: 'var(--bg-2)', border: `1px solid ${integ.enabled ? 'var(--border)' : 'var(--bg-4)'}`,
            borderRadius: 'var(--radius)', padding: '10px 12px',
            opacity: integ.enabled ? 1 : 0.5,
            transition: 'opacity 0.2s',
          }}>
            <Globe size={14} color={integ.enabled ? 'var(--accent)' : 'var(--text-3)'} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-head)', color: 'var(--text)' }}>
                {integ.name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {integ.base_url}
              </div>
            </div>
            <button
              onClick={() => onToggle(integ.id, !integ.enabled)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: integ.enabled ? 'var(--green)' : 'var(--text-3)', padding: 2 }}
              title={integ.enabled ? 'Disable' : 'Enable'}
            >
              {integ.enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
            </button>
            <button
              onClick={() => onDelete(integ.id)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 2 }}
              title="Delete"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
        {integrations.length === 0 && !showForm && (
          <div style={{ textAlign: 'center', color: 'var(--text-3)', fontSize: 12, padding: '16px 0' }}>
            No integrations configured
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [prompt, setPrompt] = useState('')
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [agents, setAgents] = useState([])
  const [integrations, setIntegrations] = useState([])
  const [activeTab, setActiveTab] = useState('prompt')  // prompt | integrations
  const [serverOk, setServerOk] = useState(null)
  const fileRef = useRef()
  const textRef = useRef()

  // ── Load initial data ──
  useEffect(() => {
    fetch('/health')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setServerOk(true) })
      .catch(() => setServerOk(false))

    fetch('/agents').then(r => r.json()).then(setAgents).catch(() => {})
    fetch('/integrations').then(r => r.json()).then(setIntegrations).catch(() => {})
  }, [])

  // ── Auto-resize textarea ──
  useEffect(() => {
    if (textRef.current) {
      textRef.current.style.height = 'auto'
      textRef.current.style.height = Math.min(textRef.current.scrollHeight, 180) + 'px'
    }
  }, [prompt])

  const handleFileAdd = (e) => {
    const picked = Array.from(e.target.files || [])
    setFiles(f => [...f, ...picked])
    e.target.value = ''
  }

  const handleSubmit = async () => {
    if (!prompt.trim() || loading) return
    setLoading(true)
    setResult(null)

    try {
      let response
      if (files.length > 0) {
        const fd = new FormData()
        fd.append('prompt', prompt)
        files.forEach(f => fd.append('files', f))
        response = await fetch('/orchestrate/with-files', { method: 'POST', body: fd })
      } else {
        response = await fetch('/orchestrate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
        })
      }
      const data = await response.json()
      setResult(data)
    } catch (err) {
      setResult({ status: 'failed', error: err.message })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit()
  }

  // Integration ops
  const addIntegration = async (payload) => {
    const res = await fetch('/integrations', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = await res.json()
    setIntegrations(i => [...i, data])
  }

  const deleteIntegration = async (id) => {
    await fetch(`/integrations/${id}`, { method: 'DELETE' })
    setIntegrations(i => i.filter(x => x.id !== id))
  }

  const toggleIntegration = async (id, enabled) => {
    const res = await fetch(`/integrations/${id}/toggle?enabled=${enabled}`, { method: 'PATCH' })
    const data = await res.json()
    setIntegrations(i => i.map(x => x.id === id ? data : x))
  }

  // ── Layout ──
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* ── Sidebar ── */}
      <aside style={{
        width: 260, flexShrink: 0,
        background: 'var(--bg-2)', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Activity size={16} color="var(--bg)" />
            </div>
            <div>
              <div style={{ fontFamily: 'var(--font-head)', fontWeight: 800, fontSize: 14, letterSpacing: '-0.01em' }}>
                ORCHESTRATOR
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.08em' }}>
                MULTI-AGENT LLM
              </div>
            </div>
          </div>
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Dot color={serverOk === null ? 'var(--yellow)' : serverOk ? 'var(--green)' : 'var(--red)'} pulse={serverOk === null} />
            <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
              {serverOk === null ? 'Connecting…' : serverOk ? 'Server online' : 'Server offline'}
            </span>
          </div>
        </div>

        {/* Agents */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.07em', marginBottom: 10 }}>
            ACTIVE AGENTS
          </div>
          {agents.length === 0
            ? <div style={{ fontSize: 12, color: 'var(--text-3)' }}>Loading…</div>
            : agents.map(a => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Cpu size={12} color="var(--accent)" />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', fontFamily: 'var(--font-head)' }}>
                    {a.id}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-3)' }}>
                    {a.provider} / {a.model}
                  </div>
                </div>
              </div>
            ))
          }
        </div>

        {/* Nav tabs */}
        <div style={{ padding: '12px 12px 0' }}>
          {[
            { key: 'prompt', icon: <Zap size={13} />, label: 'Prompt' },
            { key: 'integrations', icon: <Globe size={13} />, label: 'Integrations' },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 10px', borderRadius: 6, marginBottom: 2,
                background: activeTab === tab.key ? 'var(--accent-dim)' : 'none',
                border: activeTab === tab.key ? '1px solid #00e5ff22' : '1px solid transparent',
                color: activeTab === tab.key ? 'var(--accent)' : 'var(--text-3)',
                cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-mono)',
                textAlign: 'left', transition: 'all 0.15s',
              }}
            >
              {tab.icon} {tab.label}
              {tab.key === 'integrations' && integrations.length > 0 && (
                <Badge color="accent">{integrations.filter(i => i.enabled).length}</Badge>
              )}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Footer */}
        <div style={{ padding: 16, borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.05em' }}>
            v2.0 · FastAPI + React
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)' }}>

        {/* Top bar */}
        <div style={{
          padding: '14px 24px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 12,
          background: 'var(--bg-2)',
        }}>
          <span style={{ fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 15 }}>
            {activeTab === 'prompt' ? 'Task Prompt' : 'API Integrations'}
          </span>
          {activeTab === 'prompt' && result && (
            <Badge color={result.status === 'completed' ? 'green' : 'red'}>
              {result.status}
            </Badge>
          )}
          {activeTab === 'prompt' && result?.total_duration_seconds && (
            <span style={{ fontSize: 11, color: 'var(--text-3)', marginLeft: 'auto' }}>
              <Clock size={11} style={{ display: 'inline', marginRight: 4 }} />
              {fmt(result.total_duration_seconds)} total
            </span>
          )}
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>

          {/* ── Prompt Tab ── */}
          {activeTab === 'prompt' && (
            <div style={{ maxWidth: 800, margin: '0 auto' }}>

              {/* Input card */}
              <div style={{
                background: 'var(--bg-2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', overflow: 'hidden', marginBottom: 20,
              }}>
                <textarea
                  ref={textRef}
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Describe your task — the controller will decompose it and dispatch to agents…"
                  style={{
                    width: '100%', minHeight: 80, resize: 'none',
                    background: 'none', border: 'none', outline: 'none',
                    padding: '16px 18px', color: 'var(--text)',
                    fontFamily: 'var(--font-mono)', fontSize: 14, lineHeight: 1.6,
                  }}
                />

                {/* File chips */}
                {files.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '0 18px 12px' }}>
                    {files.map((f, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 5,
                        background: 'var(--bg-4)', border: '1px solid var(--border)',
                        borderRadius: 4, padding: '3px 8px',
                      }}>
                        <Paperclip size={10} color="var(--accent)" />
                        <span style={{ fontSize: 11, color: 'var(--text-2)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {f.name}
                        </span>
                        <button
                          onClick={() => setFiles(fs => fs.filter((_, j) => j !== i))}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0, lineHeight: 1 }}
                        >
                          <X size={10} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Toolbar */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '10px 14px', borderTop: '1px solid var(--border)',
                  background: 'var(--bg-3)',
                }}>
                  <input ref={fileRef} type="file" multiple onChange={handleFileAdd} style={{ display: 'none' }} />
                  <button
                    onClick={() => fileRef.current.click()}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5,
                      background: 'none', border: '1px solid var(--border)',
                      borderRadius: 5, padding: '5px 10px', cursor: 'pointer',
                      color: 'var(--text-3)', fontSize: 12,
                    }}
                  >
                    <Paperclip size={12} /> Attach
                  </button>

                  <div style={{ flex: 1 }} />

                  <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                    {integrations.filter(i => i.enabled).length} tool{integrations.filter(i => i.enabled).length !== 1 ? 's' : ''} active
                  </span>

                  <button
                    onClick={handleSubmit}
                    disabled={!prompt.trim() || loading}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 7,
                      background: prompt.trim() && !loading ? 'var(--accent)' : 'var(--bg-4)',
                      color: prompt.trim() && !loading ? 'var(--bg)' : 'var(--text-3)',
                      border: 'none', borderRadius: 6, padding: '7px 16px',
                      cursor: prompt.trim() && !loading ? 'pointer' : 'not-allowed',
                      fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 13,
                      transition: 'all 0.15s',
                    }}
                  >
                    {loading
                      ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Running</>
                      : <><Send size={13} /> Run  <span style={{ opacity: 0.6, fontSize: 10, fontWeight: 400 }}>⌘↵</span></>
                    }
                  </button>
                </div>
              </div>

              {/* Loading state */}
              {loading && (
                <div style={{
                  background: 'var(--bg-2)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)', padding: 20,
                  display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16,
                }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%',
                    border: '2px solid var(--bg-4)', borderTop: '2px solid var(--accent)',
                    animation: 'spin 0.8s linear infinite', flexShrink: 0,
                  }} />
                  <div>
                    <div style={{ fontFamily: 'var(--font-head)', fontWeight: 700, marginBottom: 3 }}>
                      Orchestrating…
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                      Controller decomposing task → dispatching agents concurrently
                    </div>
                  </div>
                </div>
              )}

              {/* Results */}
              {result && (
                <div style={{ animation: 'slide-in 0.3s ease' }}>

                  {/* Agent responses */}
                  {result.agent_responses?.length > 0 && (
                    <div style={{ marginBottom: 20 }}>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.07em', marginBottom: 10 }}>
                        AGENT RESPONSES — {result.agent_responses.length} AGENT{result.agent_responses.length !== 1 ? 'S' : ''}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {result.agent_responses.map(r => (
                          <AgentCard key={r.task_id} response={r} isRunning={false} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Final answer */}
                  {result.final_answer && (
                    <div style={{
                      background: 'var(--bg-2)', border: '1px solid var(--border)',
                      borderLeft: '3px solid var(--accent)',
                      borderRadius: 'var(--radius-lg)', overflow: 'hidden',
                    }}>
                      <div style={{
                        padding: '12px 18px', borderBottom: '1px solid var(--border)',
                        background: 'var(--bg-3)',
                        display: 'flex', alignItems: 'center', gap: 8,
                      }}>
                        <CheckCircle2 size={14} color="var(--accent)" />
                        <span style={{ fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: 13 }}>
                          FINAL ANSWER
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--text-3)', marginLeft: 'auto' }}>
                          {result.sub_task_count} sub-task{result.sub_task_count !== 1 ? 's' : ''}
                        </span>
                      </div>
                      <div className="md-output" style={{ padding: '18px 20px' }}>
                        <ReactMarkdown>{result.final_answer}</ReactMarkdown>
                      </div>
                    </div>
                  )}

                  {result.error && (
                    <div style={{
                      background: 'var(--red-dim)', border: '1px solid #ff446630',
                      borderRadius: 'var(--radius-lg)', padding: 16,
                    }}>
                      <div style={{ color: 'var(--red)', fontWeight: 600, marginBottom: 6 }}>Error</div>
                      <div style={{ fontSize: 13, color: 'var(--text-2)' }}>{result.error}</div>
                    </div>
                  )}
                </div>
              )}

              {/* Empty state */}
              {!result && !loading && (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-3)' }}>
                  <Activity size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                  <div style={{ fontFamily: 'var(--font-head)', fontSize: 15, marginBottom: 6, color: 'var(--text-2)' }}>
                    Ready to orchestrate
                  </div>
                  <div style={{ fontSize: 12 }}>
                    Type a prompt above and press Run — the controller will decompose your task<br />
                    and dispatch sub-tasks to your agents concurrently.
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Integrations Tab ── */}
          {activeTab === 'integrations' && (
            <div style={{ maxWidth: 600, margin: '0 auto' }}>
              <div style={{
                background: 'var(--bg-2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', padding: 20,
              }}>
                <IntegrationsPanel
                  integrations={integrations}
                  onAdd={addIntegration}
                  onDelete={deleteIntegration}
                  onToggle={toggleIntegration}
                />
              </div>

              <div style={{
                marginTop: 16, background: 'var(--bg-2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', padding: 20,
              }}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.07em', marginBottom: 12 }}>
                  HOW INTEGRATIONS WORK
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.7 }}>
                  Enabled integrations are injected into each agent's system context as available tools.
                  The agent can reference them in its reasoning and include tool results in its response.
                  Use the path template with <code style={{ background: 'var(--bg-4)', padding: '1px 5px', borderRadius: 3, color: 'var(--accent)' }}>{'{param}'}</code> placeholders
                  to define how parameters map to the URL.
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
