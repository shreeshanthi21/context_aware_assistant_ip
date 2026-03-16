import { useState, useEffect, useRef } from "react";

const API = "http://127.0.0.1:8000";
const USER_ID = "ridhu";

function formatDate(iso) {
return new Date(iso).toLocaleString();
}

function Bubble({ role, text }) {
const isUser = role === "user";

return (
<div style={{ textAlign: isUser ? "right" : "left", marginBottom: 10 }}>
<div
style={{
display: "inline-block",
padding: "10px 14px",
borderRadius: 8,
background: isUser ? "#2563eb33" : "#111827",
border: "1px solid #1f2937",
maxWidth: "80%"
}}
>
{text} </div> </div>
);
}

export default function App() {

const [messages, setMessages] = useState([
{ role: "assistant", text: "Try: remind me in 1 minute to drink water" }
]);

const [reminders, setReminders] = useState([]);
const [input, setInput] = useState("");
const chatRef = useRef(null);

const headers = {
"Content-Type": "application/json",
"X-User-ID": USER_ID
};

const loadReminders = async () => {
try {
const res = await fetch(`${API}/reminders`, { headers });


  if (!res.ok) return;

  const data = await res.json();

  const mapped = data.map(r => ({
  id: r.id,
  task: r.message,
  time: r.trigger_at,
  status: r.status
}));
  setReminders(mapped);

} catch (err) {
  console.log("Reminder fetch failed");
}


};

useEffect(() => {
loadReminders();
}, []);

useEffect(() => {
if (chatRef.current) {
chatRef.current.scrollTop = chatRef.current.scrollHeight;
}
}, [messages]);

const send = async () => {


const msg = input.trim();
if (!msg) return;

setInput("");

setMessages(prev => [...prev, { role: "user", text: msg }]);

try {

  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message: msg })
  });

  const data = await res.json();

  setMessages(prev => [
    ...prev,
    { role: "assistant", text: data.reply }
  ]);

  loadReminders();

} catch {
  setMessages(prev => [
    ...prev,
    { role: "assistant", text: "Server error" }
  ]);
}


};

const cancelReminder = async (id) => {


await fetch(`${API}/reminders/${id}`, {
  method: "DELETE",
  headers
});

loadReminders();


};

return (
<div style={{ padding: 40, background: "#020617", minHeight: "100vh", color: "white" }}>


  <h2>Context Aware Reminder Assistant</h2>

  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40 }}>

    <div>
      <h3>Chat</h3>

      <div
        ref={chatRef}
        style={{
          height: 300,
          overflowY: "auto",
          marginBottom: 10
        }}
      >
        {messages.map((m, i) => (
          <Bubble key={i} role={m.role} text={m.text} />
        ))}
      </div>

      <input
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => e.key === "Enter" && send()}
        placeholder="remind me in 1 minute to drink water"
        style={{ padding: 10, width: 300, marginRight: 10 }}
      />

      <button onClick={send}>
        Send
      </button>
    </div>

    <div>

      <h3>Reminders</h3>

      {reminders.map(r => (
        <div key={r.id} style={{ marginBottom: 10 }}>
          {r.task} — {formatDate(r.time)}

          {r.status === "pending" && (
            <button
              onClick={() => cancelReminder(r.id)}
              style={{ marginLeft: 10 }}
            >
              Cancel
            </button>
          )}
        </div>
      ))}
    </div>

  </div>

</div>


);
}
