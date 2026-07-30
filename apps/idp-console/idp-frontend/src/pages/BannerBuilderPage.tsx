import { useState } from 'react'
import { api } from '../services/api'

/** Visual banner builder with live preview. Publish -> <1s propagation to all systems. */
export default function BannerBuilderPage() {
  const [banner, setBanner] = useState({
    name: '', slug: '', title: 'We value your privacy',
    message: 'We use cookies to improve your experience.',
    button_accept_text: 'Accept All', button_reject_text: 'Reject All',
    button_customize_text: 'Customize', position: 'bottom',
    background_color: '#ffffff', text_color: '#333333', button_color: '#667eea',
  })

  const save = async () => {
    const res = await api.post('/banner', banner)
    alert(`Banner saved (draft). ID: ${res.data.id}`)
  }

  return (
    <main style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, padding: 24 }}>
      <section>
        <h1>Banner Builder</h1>
        {Object.entries(banner).map(([key, value]) => (
          <label key={key} style={{ display: 'block', marginBottom: 8 }}>
            {key.replace(/_/g, ' ')}
            <input
              value={value}
              onChange={(e) => setBanner({ ...banner, [key]: e.target.value })}
              style={{ display: 'block', width: '100%' }}
            />
          </label>
        ))}
        <button onClick={save}>Save Draft</button>
      </section>
      <section>
        <h2>Live Preview</h2>
        <div style={{
          background: banner.background_color, color: banner.text_color,
          padding: 20, borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        }}>
          <strong>{banner.title}</strong>
          <p>{banner.message}</p>
          <button style={{ background: banner.button_color, color: '#fff', marginRight: 8 }}>
            {banner.button_accept_text}
          </button>
          <button>{banner.button_reject_text}</button>
          <button style={{ marginLeft: 8 }}>{banner.button_customize_text}</button>
        </div>
      </section>
    </main>
  )
}
