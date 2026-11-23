import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useActor } from './ActorProvider'

const actors = [{ email: 'alice@east.test', label: 'Alice · East' }, { email: 'bob@west.test', label: 'Bob · West' }]

export function ActorMenu() {
  const { actorEmail, tenant, switchActor, writeInFlight } = useActor()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  return <div className="actor-menu">
    <button type="button" aria-haspopup="menu" aria-expanded={open} disabled={writeInFlight} onClick={() => setOpen(value => !value)}>{actors.find(actor => actor.email === actorEmail)?.label ?? actorEmail} ▾</button>
    {open && <div className="actor-options" role="menu" aria-label="演示管理员">{actors.map(actor => <button key={actor.email} type="button" role="menuitemradio" aria-checked={actor.email === actorEmail} onClick={() => { switchActor(actor.email); navigate('/certificates'); setOpen(false) }}>{actor.label}<small>{actor.email}</small></button>)}</div>}
    <span className="tenant-label">{tenant ? tenant.timezone : '身份确认中'}</span>
  </div>
}
