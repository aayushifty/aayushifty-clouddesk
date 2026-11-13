// Aayushifty CloudDesk 2.0 - Frontend Client Logic
// Cloud-First Development & Storage Management Engine

let allMappedProjects = {};

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initQuickActions();
  initForms();

  // Initial data fetch
  fetchTelemetry();
  fetchDriveStatus();
  fetchCloudAnalytics();
  fetchMappedProjects();
  fetchProjects();
  fetchCacheStatus();
  fetchBackups();
  fetchCredentials();

  fetchGuard();
  initCloudWorkspace();

  // Polling loops - skipped while the window is minimised/hidden, so an idle
  // dashboard costs no CPU, disk or network on the 8 GB laptop.
  const whenVisible = fn => () => { if (!document.hidden) fn(); };
  setInterval(whenVisible(fetchTelemetry), 3000);
  setInterval(whenVisible(fetchDriveStatus), 6000);
  setInterval(whenVisible(fetchCloudAnalytics), 60000); // server caches the scan anyway
  setInterval(whenVisible(fetchGuard), 30000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) { fetchTelemetry(); fetchDriveStatus(); fetchGuard(); }
  });
});

// ---------------- CLOUDDESK GUARD ----------------
async function fetchGuard() {
  try {
    const res = await fetch("/api/guard");
    if (!res.ok) return;
    const g = await res.json();
    const badge = document.getElementById("guard-badge");
    const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    if (!g.running) {
      if (badge) { badge.textContent = "Offline"; badge.className = "badge orange"; }
      set("guard-ram", "--");
      set("guard-disk", g.detail || "Not running");
      return;
    }
    const alert = g.ram_alert || g.disk_alert;
    if (badge) { badge.textContent = alert ? "Acting" : "Watching"; badge.className = `badge ${alert ? "orange" : "green"}`; }
    set("guard-ram", `${g.ram_percent}% RAM`);
    set("guard-disk", `C: free ${g.disk_free_gb} GB`);
    set("guard-last-action", (g.actions && g.actions.length) ? `${g.ts}: ${g.actions.join("; ")}` : `Last check ${g.ts}`);
  } catch (err) {
    console.error("Guard error:", err);
  }
}

// Tab Navigation
function initTabs() {
  const buttons = document.querySelectorAll(".nav-item");
  const panels = document.querySelectorAll(".tab-panel");

  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      buttons.forEach(b => b.classList.remove("active"));
      panels.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });
}

// Quick Actions
function initQuickActions() {
  document.getElementById("btn-quick-workspace")?.addEventListener("click", () => {
    fetch("/api/actions/open-workspace", { method: "POST" });
  });

  document.getElementById("btn-quick-drive")?.addEventListener("click", () => {
    fetch("/api/actions/open-drive", { method: "POST" });
  });

  document.getElementById("btn-quick-vscode")?.addEventListener("click", () => {
    fetch("/api/actions/open-vscode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: "D:\\CloudDesk\\Workspace" })
    });
  });

  document.getElementById("btn-quick-colab")?.addEventListener("click", () => {
    fetch("/api/actions/open-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: "https://colab.research.google.com/" })
    });
  });

  document.getElementById("btn-open-workspace-folder")?.addEventListener("click", () => {
    fetch("/api/actions/open-workspace", { method: "POST" });
  });

  document.getElementById("btn-init-cloud-folders")?.addEventListener("click", async () => {
    const res = await fetch("/api/drive/init-folders", { method: "POST" });
    const data = await res.json();
    alert(data.message);
    fetchDriveStatus();
  });

  document.getElementById("btn-refresh-cloud-analytics")?.addEventListener("click", () => fetchCloudAnalytics(true));

  document.getElementById("btn-generate-colab")?.addEventListener("click", async () => {
    const res = await fetch("/api/colab/generate", { method: "POST" });
    const data = await res.json();
    alert(`Colab Accelerator Notebook Generated at:\n${data.path}`);
  });

  document.getElementById("btn-open-colab-web")?.addEventListener("click", () => {
    fetch("/api/actions/open-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: "https://colab.research.google.com/" })
    });
  });

  document.getElementById("btn-open-codespaces")?.addEventListener("click", () => {
    fetch("/api/actions/open-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: "https://github.com/codespaces" })
    });
  });

  document.getElementById("btn-refresh-backups")?.addEventListener("click", fetchBackups);

  // New Project Form Toggle
  document.getElementById("btn-modal-new-project")?.addEventListener("click", () => {
    const box = document.getElementById("new-project-box");
    box.style.display = box.style.display === "none" ? "block" : "none";
  });

  document.getElementById("btn-cancel-new-project")?.addEventListener("click", () => {
    document.getElementById("new-project-box").style.display = "none";
  });

  document.getElementById("btn-submit-create-project")?.addEventListener("click", createNewProject);

  // Search Filter for Projects
  document.getElementById("project-search-input")?.addEventListener("input", (e) => {
    filterProjects(e.target.value.toLowerCase());
  });
}

// ---------------- TELEMETRY & HARDWARE ----------------
async function fetchTelemetry() {
  try {
    const res = await fetch("/api/telemetry");
    if (!res.ok) return;
    const data = await res.json();

    // 1. RAM
    const ram = data.memory;
    document.getElementById("ram-used").innerText = ram.used_gb;
    document.getElementById("ram-free").innerText = `Free: ${ram.free_gb} GB`;
    document.getElementById("ram-percent").innerText = `${ram.percent}%`;
    const ramBar = document.getElementById("ram-progress");
    ramBar.style.width = `${ram.percent}%`;

    const ramBadge = document.getElementById("ram-badge");
    ramBadge.innerText = ram.pressure.toUpperCase();
    ramBadge.className = "badge " + (ram.percent > 85 ? "red" : ram.percent > 75 ? "orange" : "green");

    // 2. CPU
    const cpu = data.cpu;
    document.getElementById("cpu-percent").innerText = `${cpu.percent}%`;
    document.getElementById("cpu-progress").style.width = `${cpu.percent}%`;
    document.getElementById("cpu-cores").innerText = `${cpu.physical_cores} Cores / ${cpu.logical_cores} Threads`;
    document.getElementById("cpu-freq").innerText = `${cpu.frequency_mhz} MHz`;

    // 3. GPU
    const gpu = data.gpu;
    if (gpu.available) {
      document.getElementById("gpu-vram-used").innerText = `${gpu.vram_used_mb} MB`;
      document.getElementById("gpu-progress").style.width = `${gpu.vram_percent}%`;
      document.getElementById("gpu-temp").innerText = `Temp: ${gpu.temperature_c}°C`;
      document.getElementById("gpu-util").innerText = `Load: ${gpu.gpu_util_percent}%`;
    }

    // 4. Disks List
    const diskContainer = document.getElementById("disk-drives-list");
    if (diskContainer && data.disks) {
      diskContainer.innerHTML = data.disks.map(d => {
        const barColor = d.percent > 90 && !d.is_cloud ? "bg-red" : "bg-blue";
        return `
          <div class="drive-item">
            <div class="drive-item-header">
              <strong>${d.drive} ${d.is_cloud ? "(Google Drive Stream)" : d.drive.startsWith("D") ? "(Active Workspace NVMe)" : "(Local SSD)"}</strong>
              <span>${d.used_gb} GB used / ${d.free_gb} GB free (${d.percent}%)</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar ${barColor}" style="width: ${d.percent}%"></div>
            </div>
          </div>
        `;
      }).join("");
    }

    // 5. Top Processes
    const procContainer = document.getElementById("processes-list");
    if (procContainer && data.top_processes) {
      procContainer.innerHTML = data.top_processes.map(p => `
        <div class="proc-row">
          <span class="proc-name">${p.name} <span class="subtext">(${p.pid})</span></span>
          <span class="proc-ram">${p.ram_mb} MB</span>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Telemetry error:", err);
  }
}

// ---------------- GOOGLE DRIVE & CLOUD STORAGE ----------------
async function fetchDriveStatus() {
  try {
    const res = await fetch("/api/drive/status");
    if (!res.ok) return;
    const data = await res.json();

    const badge = document.getElementById("gdrive-badge");
    const mountEl = document.getElementById("gdrive-mount");
    const modeEl = document.getElementById("gdrive-mode");
    const foldersStatus = document.getElementById("gdrive-folders-status");
    const btnAction = document.getElementById("btn-fix-drive");

    if (data.mount_point) {
      badge.innerText = "STREAMING ACTIVE";
      badge.className = "badge green";
      mountEl.innerText = data.mount_point;
      modeEl.innerText = "Primary Cloud Storage (Stream Files)";
      foldersStatus.innerText = data.folders_initialized ? "All 9 Cloud Folders Ready" : "Folders Pending";
      btnAction.innerText = "Explore G:\\";
      btnAction.onclick = () => fetch("/api/actions/open-drive", { method: "POST" });
    } else if (data.installed) {
      badge.innerText = "INSTALLED (OFFLINE)";
      badge.className = "badge orange";
      mountEl.innerText = "Offline";
      modeEl.innerText = "Launch Google Drive to mount G:\\";
      btnAction.innerText = "Start";
      btnAction.onclick = () => alert("Please launch Google Drive from your Windows Start Menu.");
    } else {
      badge.innerText = "INSTALLER READY";
      badge.className = "badge blue";
      mountEl.innerText = "Setup Staged";
      modeEl.innerText = "Run GoogleDriveSetup.exe to mount G:\\";
      btnAction.innerText = "Install Drive";
      btnAction.onclick = async () => {
        const resp = await fetch("/api/actions/install-drive", { method: "POST" });
        const d = await resp.json();
        alert(d.message);
      };
    }

    // Render cloud folders
    const container = document.getElementById("cloud-folders-container");
    if (container && data.folders) {
      container.innerHTML = Object.entries(data.folders).map(([name, exists]) => `
        <div class="cloud-folder-item ${exists ? 'active' : ''}">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="${exists ? '#10b981' : '#94a3b8'}"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
          <div>
            <div class="cloud-folder-name">${name}/</div>
            <span class="subtext">${exists ? 'Central Cloud Store' : 'Pending init'}</span>
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Drive status error:", err);
  }
}

// ---------------- CLOUD ANALYTICS & CATEGORIES ----------------
async function fetchCloudAnalytics(refresh = false) {
  try {
    const res = await fetch(`/api/cloud/analytics${refresh === true ? "?refresh=true" : ""}`);
    if (!res.ok) return;
    const data = await res.json();

    const cloud = data.cloud;
    const quota = cloud.quota;
    const subtext = document.getElementById("cloud-quota-subtext");
    if (subtext) {
      if (cloud.google_drive_online) {
        subtext.innerText = `Actual Dynamic Quota: ${quota.used_gb} GB Used / ${quota.free_gb} GB Free (${quota.percent}% Allocated)`;
      } else {
        subtext.innerText = `Google Drive Offline. Ready to mount ~5 TB cloud capacity.`;
      }
    }

    const catGrid = document.getElementById("cloud-categories-grid");
    if (catGrid && cloud.category_breakdown) {
      catGrid.innerHTML = Object.entries(cloud.category_breakdown).map(([cat, info]) => `
        <div class="card metric-card" style="padding: 12px;">
          <div class="card-header">
            <span class="card-label">${cat}</span>
            <span class="badge blue">${info.files_count} files</span>
          </div>
          <div class="metric-main">
            <h3>${info.size_gb > 1 ? info.size_gb + ' GB' : info.size_mb + ' MB'}</h3>
          </div>
          <div class="card-footer">
            <span>Google Drive Central</span>
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Cloud analytics error:", err);
  }
}

// ---------------- PROJECT LIFECYCLE MANAGEMENT ----------------
async function fetchMappedProjects() {
  try {
    const res = await fetch("/api/projects/mappings");
    if (!res.ok) return;
    allMappedProjects = await res.json();
    renderMappedProjects(allMappedProjects);
  } catch (err) {
    console.error("Mapped projects error:", err);
  }
}

function renderMappedProjects(mappings) {
  const container = document.getElementById("mapped-projects-container");
  if (!container) return;

  const entries = Object.entries(mappings);
  if (entries.length === 0) {
    container.innerHTML = `
      <p class="empty-state">No projects registered yet. Click <strong>+ New Project</strong> above to create your first cloud-first project in D:\\CloudDesk\\Workspace and Google Drive.</p>
    `;
    return;
  }

  container.innerHTML = `
    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
      <thead>
        <tr style="border-bottom: 1px solid var(--border-color); text-align: left; color: var(--text-muted);">
          <th style="padding: 8px;">Project</th>
          <th style="padding: 8px;">Local Workspace (D:)</th>
          <th style="padding: 8px;">Google Drive Central (G:)</th>
          <th style="padding: 8px;">Status</th>
          <th style="padding: 8px; text-align: right;">Lifecycle Actions</th>
        </tr>
      </thead>
      <tbody>
        ${entries.map(([name, meta]) => `
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
            <td style="padding: 10px 8px; font-weight: 700; color: #fff;">${name}</td>
            <td style="padding: 10px 8px; font-family: monospace; font-size: 11.5px; color: var(--accent-blue);">${meta.local_path}</td>
            <td style="padding: 10px 8px; font-family: monospace; font-size: 11.5px; color: var(--accent-green);">${meta.cloud_path}</td>
            <td style="padding: 10px 8px;">
              <span class="badge ${meta.status === 'completed' ? 'purple' : 'green'}">${meta.status.toUpperCase()}</span>
            </td>
            <td style="padding: 10px 8px; text-align: right;">
              <button class="btn btn-secondary btn-xs" onclick="syncProjectAssets('${name}')">Sync Assets</button>
              <button class="btn btn-secondary btn-xs" onclick="openInVSCode('${meta.local_path.replace(/\\/g, '\\\\')}')">VS Code</button>
              <button class="btn btn-primary btn-xs" onclick="completeProject('${name}')">Complete & Archive</button>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function filterProjects(query) {
  if (!query) {
    renderMappedProjects(allMappedProjects);
    return;
  }
  const filtered = {};
  for (const [name, meta] of Object.entries(allMappedProjects)) {
    if (name.toLowerCase().includes(query) || meta.local_path.toLowerCase().includes(query)) {
      filtered[name] = meta;
    }
  }
  renderMappedProjects(filtered);
}

async function createNewProject() {
  const nameInput = document.getElementById("new-proj-name");
  const gitInput = document.getElementById("new-proj-git");
  const name = nameInput.value.trim();

  if (!name) {
    alert("Please enter a project name.");
    return;
  }

  try {
    const res = await fetch("/api/projects/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_name: name,
        init_git: gitInput.value === "true"
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Project Created Successfully!\nLocal: ${data.local_path}\nCloud: ${data.cloud_path}`);
      nameInput.value = "";
      document.getElementById("new-project-box").style.display = "none";
      fetchMappedProjects();
    } else {
      alert(`Failed: ${data.detail || "Unknown error"}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

window.syncProjectAssets = async (projectName) => {
  if (!confirm(`Synchronize assets for '${projectName}' to Google Drive?\n(Strict security active: .env and credentials will never be synced).`)) return;

  try {
    const res = await fetch(`/api/projects/sync/${projectName}`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      alert(`Sync Complete for ${projectName}!\nSynced: ${data.synced_count} assets with verified SHA256 hashes.`);
      fetchCloudAnalytics();
      fetchMappedProjects();
    } else {
      alert(`Sync Failed: ${data.detail || data.error}`);
    }
  } catch (err) {
    alert(`Error syncing: ${err.message}`);
  }
};

window.completeProject = async (projectName) => {
  const evict = confirm(
    `Complete and Archive '${projectName}'?\n\n` +
    `1. Creates a clean, verified source archive on Google Drive.\n` +
    `2. Tests ZIP CRC32 and SHA256 integrity.\n` +
    `3. Safely removes local build artifacts (node_modules/.venv) to free local SSD space.\n\n` +
    `Click OK to archive and reclaim local SSD space.`
  );
  if (!evict) return;

  try {
    const res = await fetch("/api/projects/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_name: projectName, evict_local_build_artifacts: true })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Project Completed & Archived!\nArchive: ${data.archive_name}\nReclaimed Local Space: ${data.reclaimed_local_mb} MB\nRecoverable from Cloud: Yes!`);
      fetchMappedProjects();
      fetchCloudAnalytics();
      fetchBackups();
    } else {
      alert(`Archive Failed: ${data.detail || "Error"}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
};

// ---------------- CACHE & MODEL MANAGER ----------------
async function fetchCacheStatus() {
  try {
    const res = await fetch("/api/cache/status");
    if (!res.ok) return;
    const data = await res.json();

    const metersContainer = document.getElementById("cache-meters-container");
    if (metersContainer && data.caches) {
      metersContainer.innerHTML = Object.entries(data.caches).map(([key, c]) => `
        <div class="drive-item" style="margin-bottom: 8px;">
          <div class="drive-item-header">
            <strong>${key.replace('_', ' ').toUpperCase()}</strong>
            <span>${c.used_gb} GB / ${c.limit_gb} GB (${c.percent}%)</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar ${c.percent >= 85 ? 'bg-red' : 'bg-purple'}" style="width: ${Math.min(c.percent, 100)}%"></div>
          </div>
          <span class="subtext">${c.path}</span>
        </div>
      `).join("");
    }

    const cachedModelsContainer = document.getElementById("cached-models-list");
    if (cachedModelsContainer && data.cached_models) {
      if (data.cached_models.length === 0) {
        cachedModelsContainer.innerHTML = '<p class="empty-state">No models currently cached in D:\\CloudDesk\\ModelCache.</p>';
      } else {
        cachedModelsContainer.innerHTML = data.cached_models.map(m => `
          <div class="action-row" style="margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.02); border-radius: 6px;">
            <div>
              <strong>${m.name}</strong>
              <div class="subtext">${m.size_mb} MB • ${m.stored_in_cloud ? 'Backed up in Drive' : 'Local Only'}</div>
            </div>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-xs ${m.pinned ? 'btn-primary' : 'btn-secondary'}" onclick="togglePinModel('${m.name}', ${!m.pinned})">${m.pinned ? 'Pinned' : 'Pin'}</button>
              <button class="btn btn-xs" style="color: #ef4444;" onclick="evictModel('${m.name}')">Evict</button>
            </div>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Cache status error:", err);
  }
}

window.togglePinModel = async (assetName, pinned) => {
  await fetch("/api/cache/pin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_name: assetName, pinned })
  });
  fetchCacheStatus();
};

window.evictModel = async (modelName) => {
  if (!confirm(`Safely evict '${modelName}' from local D:\\ cache?\n(If no cloud backup exists, CloudDesk will automatically upload it to Google Drive first before eviction).`)) return;
  try {
    const res = await fetch("/api/cache/evict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_name: modelName })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Model Evicted!\nReclaimed: ${data.reclaimed_mb} MB\nGoogle Drive Copy: Preserved.`);
      fetchCacheStatus();
      fetchTelemetry();
    } else {
      alert(`Eviction failed: ${data.detail}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
};

// ---------------- EXISTING WORKSPACES & REPOS ----------------
async function fetchProjects() {
  try {
    const res = await fetch("/api/projects");
    if (!res.ok) return;
    const data = await res.json();

    const localContainer = document.getElementById("local-projects-container");
    if (localContainer && data.local_projects) {
      localContainer.innerHTML = data.local_projects.map(p => `
        <div class="project-card">
          <div>
            <div class="project-name">${p.name}</div>
            <div class="subtext" style="word-break: break-all; margin: 4px 0;">${p.path}</div>
            <div class="project-tags">
              ${p.stack.map(s => `<span class="tag">${s}</span>`).join("")}
              ${p.is_git ? '<span class="tag">Git</span>' : ''}
              ${p.has_node_modules ? '<span class="tag" style="color:#f59e0b">node_modules</span>' : ''}
            </div>
          </div>
          <div style="display:flex; gap:8px; margin-top:8px;">
            <button class="btn btn-secondary btn-xs" onclick="openInVSCode('${p.path.replace(/\\/g, '\\\\')}')">VS Code</button>
            <button class="btn btn-secondary btn-xs" onclick="openInExplorer('${p.path.replace(/\\/g, '\\\\')}')">Explorer</button>
            <button class="btn btn-primary btn-xs" onclick="setBackupProject('${p.path.replace(/\\/g, '\\\\')}')">Backup</button>
          </div>
        </div>
      `).join("");
    }

    const reposContainer = document.getElementById("github-repos-container");
    if (reposContainer && data.github_repositories) {
      reposContainer.innerHTML = data.github_repositories.map(r => `
        <div class="repo-card">
          <div>
            <div class="repo-name">${r.name}</div>
            <div class="subtext">${r.description || 'No description provided.'}</div>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="badge ${r.isPrivate ? 'orange' : 'green'}">${r.isPrivate ? 'Private' : 'Public'}</span>
            <a href="${r.url}" target="_blank" class="btn btn-secondary btn-xs">View on GitHub</a>
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Projects error:", err);
  }
}

// ---------------- BACKUPS LIST ----------------
async function fetchBackups() {
  try {
    const res = await fetch("/api/backup/list");
    if (!res.ok) return;
    const data = await res.json();

    const container = document.getElementById("backups-list");
    if (container) {
      if (data.length === 0) {
        container.innerHTML = '<p class="empty-state">No archives created yet. Use the form on the left to create a verified backup.</p>';
      } else {
        container.innerHTML = data.map(b => `
          <div class="action-row" style="margin-bottom:8px; padding:8px 10px; background:rgba(255,255,255,0.02); border-radius:6px;">
            <div>
              <strong>${b.name}</strong>
              <div class="subtext">${b.location} • ${b.size_mb} MB • ${b.modified}</div>
            </div>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-secondary btn-xs" onclick="openInExplorer('${b.path.replace(/\\/g, '\\\\')}')">Show</button>
              <button class="btn btn-primary btn-xs" onclick="restoreArchive('${b.path.replace(/\\/g, '\\\\')}')">Restore</button>
            </div>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Backups list error:", err);
  }
}

window.restoreArchive = async (archivePath) => {
  if (!confirm(`Restore project from archive into D:\\CloudDesk\\Workspace?\n\nPath: ${archivePath}`)) return;
  try {
    const res = await fetch("/api/projects/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ archive_path: archivePath })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Restoration Successful!\nProject: ${data.project_name}\nLocation: ${data.destination}`);
      fetchMappedProjects();
    } else {
      alert(`Restore failed: ${data.detail}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
};

// ---------------- CREDENTIALS VAULT ----------------
async function fetchCredentials() {
  try {
    const res = await fetch("/api/credentials/list");
    if (!res.ok) return;
    const data = await res.json();

    const container = document.getElementById("credentials-list");
    if (container) {
      container.innerHTML = data.map(c => `
        <div class="action-row" style="margin-bottom:10px; padding:10px; background:rgba(255,255,255,0.02); border-radius:8px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <strong>${c.name}</strong>
              <span class="badge ${c.configured ? 'green' : 'orange'}">${c.configured ? 'Configured' : 'Missing'}</span>
            </div>
            <p class="subtext">${c.desc}</p>
            ${c.configured ? `<span style="font-family:monospace; font-size:12px; color:#a855f7;">${c.masked_preview}</span>` : ''}
          </div>
          <div style="display:flex; gap:8px;">
            <a href="${c.url}" target="_blank" class="btn btn-secondary btn-xs">Get Key</a>
            ${c.configured ? `<button class="btn btn-xs" style="color:#ef4444" onclick="deleteKey('${c.key_code}')">Delete</button>` : ''}
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Credentials error:", err);
  }
}

// ---------------- FORMS ----------------
function initForms() {
  document.getElementById("backup-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const projectPath = document.getElementById("backup-project-path").value.trim();
    const destType = document.getElementById("backup-dest-type").value;
    const submitBtn = document.getElementById("btn-start-backup");

    submitBtn.disabled = true;
    submitBtn.innerText = "Creating Verified Clean Backup...";

    try {
      const res = await fetch("/api/backup/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_path: projectPath,
          destination: destType === "local_d" ? "D:\\CloudDesk\\Recovery\\Backups" : "G:\\My Drive\\Backups\\Projects"
        })
      });

      const data = await res.json();
      if (res.ok) {
        alert(`Backup Successful!\nArchive: ${data.archive_name}\nCompressed: ${data.compressed_size_mb} MB (${data.compression_ratio_percent}% saved)\nSHA256: ${data.sha256}\nExcluded Secrets (.env): ${data.excluded_sensitive_files.length}`);
        fetchBackups();
      } else {
        alert(`Backup Failed: ${data.detail || "Unknown error"}`);
      }
    } catch (err) {
      alert(`Error running backup: ${err.message}`);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = "Create Clean Backup";
    }
  });

  document.getElementById("cred-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const keyName = document.getElementById("cred-key-name").value;
    const secretVal = document.getElementById("cred-secret-val").value.trim();

    if (!secretVal) return;

    try {
      const res = await fetch("/api/credentials/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key_name: keyName, secret_value: secretVal })
      });

      if (res.ok) {
        alert(`${keyName} saved securely to Windows Credential Manager!`);
        document.getElementById("cred-secret-val").value = "";
        fetchCredentials();
      } else {
        const errData = await res.json().catch(() => null);
        alert(`Failed saving credential: ${errData?.detail || res.statusText || "Unknown error"}`);
      }
    } catch (err) {
      alert(`Network error saving credential: ${err.message}`);
    }
  });
}

// Global Helpers
window.openInVSCode = (path) => {
  fetch("/api/actions/open-vscode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path })
  });
};

window.openInExplorer = (path) => {
  fetch("/api/actions/open-explorer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path })
  });
};

window.setBackupProject = (path) => {
  const input = document.getElementById("backup-project-path");
  if (input) {
    input.value = path;
    const navBtn = document.querySelector('[data-tab="tab-backups"]');
    if (navBtn) navBtn.click();
  }
};

window.deleteKey = async (keyCode) => {
  if (!confirm(`Delete ${keyCode} from Windows Credential Manager?`)) return;
  const res = await fetch(`/api/credentials/${keyCode}`, { method: "DELETE" });
  if (res.ok) fetchCredentials();
};


// ---------------- CLOUD WORKSPACE (Drive = home, laptop = cache) ----------------
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function postJSON(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

function initCloudWorkspace() {
  document.getElementById("btn-ws-refresh")?.addEventListener("click", fetchWorkspace);
  document.getElementById("btn-ws-autopark")?.addEventListener("click", async e => {
    e.target.disabled = true;
    try {
      const r = await postJSON("/api/workspace/autopark", {});
      alert(`Parked: ${r.parked.length}\nSkipped: ${r.skipped.length}`);
    } catch (err) { alert(err.message); }
    e.target.disabled = false;
    fetchWorkspace();
  });
  document.getElementById("ws-projects")?.addEventListener("click", async e => {
    const btn = e.target.closest("button[data-ws-action]");
    if (!btn) return;
    const { wsAction, name } = btn.dataset;
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = wsAction === "park" ? "Saving & verifying..." : wsAction === "open" ? "Bringing down..." : "Opening...";
    try {
      const r = await postJSON(`/api/workspace/${wsAction}`, { name });
      if (wsAction === "open" && r.path) fetch("/api/actions/open-vscode", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: r.path }) });
      if (r.success === false) alert(`${r.error}\n${(r.locked || r.mismatched_files || []).slice(0, 5).join("\n")}`);
    } catch (err) { alert(err.message); }
    btn.disabled = false;
    btn.textContent = label;
    fetchWorkspace();
  });
  document.getElementById("btn-ai-test")?.addEventListener("click", askCloudAI);
  document.getElementById("ai-test-prompt")?.addEventListener("keydown", e => { if (e.key === "Enter") askCloudAI(); });
  fetchWorkspace();
  fetchAIStatus();
  setInterval(() => { if (!document.hidden && document.getElementById("tab-workspace")?.classList.contains("active")) fetchWorkspace(); }, 10000);
}

async function fetchWorkspace() {
  const grid = document.getElementById("ws-projects");
  if (!grid) return;
  try {
    const res = await fetch("/api/workspace/projects");
    const data = await res.json();
    if (!res.ok) { grid.innerHTML = `<div class="subtext">${esc(data.detail)}</div>`; return; }
    const onLaptop = data.filter(p => p.on_laptop).length;
    document.getElementById("ws-summary").textContent = `${data.length} projects · ${onLaptop} on the laptop · ${data.length - onLaptop} parked in Google Drive`;
    grid.innerHTML = data.map(p => {
      const deps = p.deps && p.deps.status ? `<span class="tag">deps: ${esc(p.deps.status)}</span>` : "";
      const main = p.on_laptop
        ? `<button class="btn btn-primary btn-xs" data-ws-action="park" data-name="${esc(p.name)}">Park to Drive</button>`
        : `<button class="btn btn-primary btn-xs" data-ws-action="open" data-name="${esc(p.name)}">Open on laptop</button>`;
      const cloud = p.github ? `<button class="btn btn-secondary btn-xs" data-ws-action="run-in-cloud" data-name="${esc(p.name)}">Run in cloud</button>` : "";
      return `
        <div class="project-card">
          <div>
            <div class="project-name">${esc(p.name)}</div>
            <div class="project-tags">
              <span class="badge ${p.on_laptop ? "orange" : "green"}">${p.on_laptop ? "On laptop" : "Parked in Drive · 0 MB local"}</span>
              ${deps}
              ${p.github ? `<span class="tag">${esc(p.github)}</span>` : ""}
            </div>
          </div>
          <div style="display:flex; gap:8px; margin-top:8px;">${main}${cloud}</div>
        </div>`;
    }).join("") || `<div class="subtext">No projects yet. Put project folders in G:\\My Drive\\Projects or D:\\CloudDesk\\Workspace.</div>`;
  } catch (err) {
    console.error("Workspace error:", err);
  }
}

async function fetchAIStatus() {
  try {
    const s = await (await fetch("/api/ai/status")).json();
    const badge = document.getElementById("ai-badge");
    const ok = s.gemini_key_configured && s.gemini_reachable;
    if (badge) { badge.textContent = ok ? "Cloud ready" : (s.ollama_running ? "Local only" : "Offline"); badge.className = `badge ${ok ? "green" : "orange"}`; }
    document.getElementById("ai-summary").textContent =
      `Default: ${s.default_model} · Gemini key ${s.gemini_key_configured ? "set" : "missing"} · Ollama fallback ${s.local_fallback ? (s.ollama_running ? "ready" : "off (Ollama not running)") : "disabled"}`;
  } catch (err) {
    console.error("AI status error:", err);
  }
}

async function askCloudAI() {
  const input = document.getElementById("ai-test-prompt");
  const out = document.getElementById("ai-test-output");
  if (!input?.value.trim()) return;
  out.textContent = "Thinking in the cloud...";
  try {
    const res = await fetch("/v1/chat/completions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: "auto", messages: [{ role: "user", content: input.value }] })
    });
    const data = await res.json();
    const backend = res.headers.get("X-CloudDesk-Backend") || "?";
    out.textContent = res.ok
      ? `${data.choices?.[0]?.message?.content ?? "(empty)"}\n\n— answered by ${backend} (${data.model || ""})`
      : `Error: ${JSON.stringify(data.error || data.detail || data)}`;
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
}
