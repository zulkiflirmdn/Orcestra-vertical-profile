import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle

# --- Parameter Konfigurasi ---
RADIUS_KM = 150.0
NUM_SONDES = 12
PRESSURE_LEVELS = np.linspace(1000, 100, 100) # hPa
FRAMES = 100

# --- Fungsi untuk Mensimulasikan Angin (Divergensi) ---
# Menggunakan model konseptual sederhana:
# Bottom-Heavy: Konvergensi kuat di bawah (asendensi kuat di bawah)
# Top-Heavy: Konvergensi kuat di atas (asendensi kuat di atas)

def simulate_divergence(pressure, profile_type, phase):
    """Mensimulasikan profil divergensi berdasarkan tipe profil."""
    p_star = (pressure - 100) / (1000 - 100)
    
    # Animasi "berdenyut"
    intensity = 0.5 + 0.5 * np.sin(phase) 
    
    if profile_type == 'Bottom-Heavy':
        # Divergensi = turunan dari Omega (kira-kira)
        # Omega sin(pi*p*) + sin(2*pi*p*), puncaknya di bawah
        # Konvergensi (negatif) kuat di bawah, divergensi (positif) di atas
        div = -1.0 * np.exp(-((pressure - 850) / 150)**2) * intensity # Konvergensi bawah
        div += 0.5 * np.exp(-((pressure - 200) / 200)**2) * intensity # Divergensi atas
        
    elif profile_type == 'Top-Heavy':
        # Konvergensi (negatif) kuat di atas, divergensi lemah/0 di bawah
        div = -1.0 * np.exp(-((pressure - 400) / 200)**2) * intensity # Konvergensi atas
        div += 0.3 * np.exp(-((pressure - 850) / 150)**2) * intensity # Divergensi/konv lemah bawah
        
    return div

def calculate_omega(divergence, pressure):
    """Menghitung Omega dengan mengintegrasikan divergensi (Persamaan Kontinuitas).
       d(omega)/dp = -Divergence -> omega = -integral(Div dp)
    """
    omega = np.zeros_like(pressure)
    # Integrasi dari atas (100 hPa) ke bawah. Asumsi omega = 0 di TOA.
    # Ingat dp adalah negatif karena array dari 1000 ke 100.
    dp = np.gradient(pressure) * 100 # Konversi hPa ke Pa untuk unit SI (Pa/s)
    
    # Simple cumulative trapezoidal integration
    for i in range(len(pressure)-2, -1, -1):
        omega[i] = omega[i+1] + (divergence[i] + divergence[i+1])/2.0 * dp[i]
        
    # Asumsi permukaan (1000hPa) omega ~ 0 (koreksi massa sederhana)
    # Untuk simulasi ini kita biarkan tanpa koreksi agar bentuk profil terlihat jelas.
    
    # Scaling untuk visualisasi (Pa/s)
    return omega / 1000.0 

# --- Setup Figure ---
fig = plt.figure(figsize=(12, 6))
fig.suptitle('Dropsonde Array & Area-Averaged Vertical Velocity ($\omega$)', fontsize=14)

# Plot 1: Lingkaran Dropsonde (Top-Down)
ax1 = plt.subplot(1, 2, 1)
ax1.set_xlim(-RADIUS_KM * 1.5, RADIUS_KM * 1.5)
ax1.set_ylim(-RADIUS_KM * 1.5, RADIUS_KM * 1.5)
ax1.set_aspect('equal')
ax1.set_title('Top-Down View (Horizontal Convergence)')
ax1.set_xlabel('X (km)')
ax1.set_ylabel('Y (km)')

circle_patch = Circle((0, 0), RADIUS_KM, fill=False, color='gray', linestyle='--')
ax1.add_patch(circle_patch)

# Posisi 12 sonde
theta = np.linspace(0, 2*np.pi, NUM_SONDES, endpoint=False)
sonde_x = RADIUS_KM * np.cos(theta)
sonde_y = RADIUS_KM * np.sin(theta)
ax1.scatter(sonde_x, sonde_y, c='blue', marker='v', s=100, label='Dropsondes')
quivers = ax1.quiver(sonde_x, sonde_y, np.zeros_like(sonde_x), np.zeros_like(sonde_y), 
                     color='red', scale=5)
ax1.legend()

# Teks Ketinggian
level_text = ax1.text(0.05, 0.95, '', transform=ax1.transAxes, fontsize=12, verticalalignment='top')
profile_text = ax1.text(0.05, 0.90, '', transform=ax1.transAxes, fontsize=12, verticalalignment='top', fontweight='bold')

# Plot 2: Profil Omega
ax2 = plt.subplot(1, 2, 2)
ax2.set_xlim(-1.5, 0.5)
ax2.set_ylim(1000, 100) # Terbalik, permukaan di bawah
ax2.set_title('Calculated Vertical Velocity Profile ($\omega$)')
ax2.set_xlabel('$\omega$ (Pa/s) [Negatif = Naik]')
ax2.set_ylabel('Pressure (hPa)')
ax2.axvline(0, color='black', linestyle='--')
line_bottom, = ax2.plot([], [], color='blue', linewidth=3, label='Bottom-Heavy')
line_top, = ax2.plot([], [], color='red', linewidth=3, label='Top-Heavy')
ax2.legend()

# --- Fungsi Update Animasi ---
current_profile = 'Bottom-Heavy'

def update(frame):
    global current_profile
    
    # Ganti profil setengah jalan
    if frame > FRAMES // 2:
        current_profile = 'Top-Heavy'
    else:
        current_profile = 'Bottom-Heavy'

    phase = frame * 2 * np.pi / (FRAMES/2)
    
    # --- Update Profil Omega ---
    div_profile = simulate_divergence(PRESSURE_LEVELS, current_profile, phase)
    omega_profile = calculate_omega(div_profile, PRESSURE_LEVELS)
    
    if current_profile == 'Bottom-Heavy':
        line_bottom.set_data(omega_profile, PRESSURE_LEVELS)
        line_top.set_data([], []) # Sembunyikan yang lain
    else:
        line_top.set_data(omega_profile, PRESSURE_LEVELS)
        line_bottom.set_data([], [])
        
    profile_text.set_text(f'Simulating: {current_profile}')

    # --- Update Vektor Angin (Top-Down) ---
    # Kita animasikan vektor angin pada satu ketinggian tertentu sebagai contoh.
    # Bottom-Heavy: konvergensi kuat di bawah (850hPa). Top-Heavy: konvergensi di atas (400hPa)
    
    if current_profile == 'Bottom-Heavy':
        display_pressure = 850
    else:
        display_pressure = 400
        
    level_text.set_text(f'Displaying winds at: {display_pressure} hPa')
    
    # Ambil nilai divergensi pada level tersebut
    idx = np.argmin(np.abs(PRESSURE_LEVELS - display_pressure))
    current_div = div_profile[idx]
    
    # Jika divergensi negatif (konvergensi), angin menuju ke pusat
    # Jika divergensi positif, angin menjauh
    u = current_div * np.cos(theta) 
    v = current_div * np.sin(theta)
    
    quivers.set_UVC(u, v)
    
    return quivers, line_bottom, line_top, level_text, profile_text

# Membuat animasi
ani = animation.FuncAnimation(fig, update, frames=FRAMES, interval=100, blit=True)

plt.tight_layout()
plt.show()