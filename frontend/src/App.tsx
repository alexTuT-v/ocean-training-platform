import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { ActorProvider, useActor } from './actor/ActorProvider'
import { ActorMenu } from './actor/ActorMenu'

function Shell() {
  const { loading, error, retry } = useActor()
  return <div className="app-shell">
    <header className="topbar"><strong>Ocean · Training Admin</strong><ActorMenu /></header>
    <div className="shell-body"><nav className="sidebar" aria-label="主导航"><NavLink to="/certificates">证书</NavLink><NavLink to="/courses">课程完成</NavLink></nav>
      <main>{loading ? <p role="status">正在确认管理员身份…</p> : error ? <div role="alert">{error}<button onClick={retry}>重试</button></div> : <Routes>
        <Route path="/" element={<Navigate to="/certificates" replace />} />
        <Route path="/certificates" element={<h1>证书</h1>} />
        <Route path="/courses" element={<h1>课程完成</h1>} />
      </Routes>}</main>
    </div>
  </div>
}

export default function App() { return <BrowserRouter><ActorProvider><Shell /></ActorProvider></BrowserRouter> }
