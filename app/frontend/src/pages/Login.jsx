import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api";
import FileConstellation from "../FileConstellation.jsx";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("clerk@zeroday.local");
  const [password, setPassword] = useState("clerk123");
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    setErr("");
    try {
      const out = await api.login(email, password);
      setToken(out.token);
      nav("/");
    } catch (ex) {
      setErr(ex.message);
    }
  }

  return (
    <div className="login">
      <FileConstellation />
      <form className="login-card" onSubmit={submit}>
        <h1>ZeroDay</h1>
        <p>Sign in to the shipping document desk. SI is the source of truth; a draft BL is checked against it.</p>
        <label>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="btn primary" type="submit">Enter desk</button>
        {err && <div className="error">{err}</div>}
        <p className="muted">Demo clerk: clerk@zeroday.local / clerk123</p>
      </form>
    </div>
  );
}
