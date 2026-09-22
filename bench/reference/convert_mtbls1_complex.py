"""Emit a complex-quadrature FID CSV (time_s,real,imag) + harness reference peaks."""
import nmrglue as ng, numpy as np, json, os

SRC = '/tmp/nmrsrc/ADG10003u_007/10'
OUT = 'data/nmr'  # harness-side output dir
os.makedirs(OUT, exist_ok=True)

dic, data = ng.bruker.read(SRC)
acq = dic['acqus']
SW_h = float(acq['SW_h'])
data = ng.bruker.remove_digital_filter(dic, data)
N = data.shape[0]
dt = 1.0 / SW_h

pdic, pdata = ng.bruker.read_pdata(SRC + '/pdata/1')
pr = pdic['procs']
SF = float(pr['SF']); OFFSET = float(pr['OFFSET']); SW_p = float(pr['SW_p'])
SW_ppm = SW_p / SF
CARRIER_PPM = OFFSET - SW_ppm / 2.0
PHC0 = float(pr['PHC0']); PHC1 = float(pr['PHC1'])
print("N=%d dt=%.6e SW_h=%.4f SF=%.9f carrier=%.5f SW_ppm=%.5f PHC0=%.3f PHC1=%.3f"
      % (N, dt, SW_h, SF, CARRIER_PPM, SW_ppm, PHC0, PHC1))

csv = os.path.join(OUT, 'fid_complex.csv')
t = np.arange(N) * dt
with open(csv, 'w') as f:
    f.write("# complex quadrature 1H FID, MTBLS1 ADG10003u_007/10 (digital filter removed)\n")
    f.write("# spectrometer_frequency_MHz=%.9f carrier_ppm=%.5f spectral_width_hz=%.4f\n" % (SF, CARRIER_PPM, SW_h))
    f.write("time_s,real,imag\n")
    for ti, z in zip(t, data):
        f.write("%.8f,%.6f,%.6f\n" % (ti, z.real, z.imag))
print("wrote", csv, os.path.getsize(csv), "bytes")

# ---- harness reference: complex processing, instrument phase, TRUE ppm axis ----
LB = 1.0
NFFT = 65536
xw = data * np.exp(-np.pi * LB * t)
X = np.fft.fftshift(np.fft.fft(xw, NFFT))
f_off = (np.arange(NFFT) - NFFT // 2) * (SW_h / NFFT)      # Hz from carrier
ppm = CARRIER_PPM + f_off / SF                              # ascending
spec = ng.proc_base.ps(np.asarray(X, dtype='complex128'), p0=-PHC0, p1=-PHC1).real
# nmrglue convention check: report both and keep the one that makes water positive
i_water = int(np.argmin(np.abs(ppm - 4.767)))
if spec[max(0,i_water-50):i_water+50].max() < 0:
    spec = -spec
np.save(OUT + '/ref_ppm.npy', ppm); np.save(OUT + '/ref_spec.npy', spec)

TARGETS = {'TSP/DSS': 0.000, 'acetate': 1.921, 'citrate': 2.549,
           'creatinine_CH3': 3.048, 'creatinine_CH2': 4.058, 'water': 4.767,
           'hippurate_7.55': 7.553, 'hippurate_7.64': 7.640, 'hippurate_7.83': 7.834}
def integrate(center, halfwin=0.03, bl=(0.06, 0.10)):
    m = (ppm >= center - halfwin) & (ppm <= center + halfwin)
    b = (((ppm >= center - bl[1]) & (ppm < center - bl[0])) |
         ((ppm > center + bl[0]) & (ppm <= center + bl[1])))
    base = spec[b].mean() if b.any() else 0.0
    dppm = abs(ppm[1] - ppm[0])
    return float(((spec[m] - base).sum()) * dppm * SF)   # x SF -> per-Hz integral

print("\nreference peaks (true ppm axis, complex processing):")
res = {}
for name, p in TARGETS.items():
    m = (ppm >= p - 0.03) & (ppm <= p + 0.03)
    idx = np.where(m)[0]
    apex = idx[np.argmax(spec[idx])]
    res[name] = {'nominal_ppm': p, 'apex_ppm': float(ppm[apex]),
                 'height': float(spec[apex]), 'integral': integrate(p)}
    print("  %-16s nominal %7.3f  apex %7.4f  height %11.4e  integral %11.4e"
          % (name, p, ppm[apex], spec[apex], res[name]['integral']))

# global top maxima (>=0.05 ppm apart) for a peak-picking reference
order = np.argsort(spec)[::-1]
picked = []
for i in order:
    if spec[i] < 0.05 * spec.max():
        break
    if all(abs(ppm[i] - ppm[j]) > 0.05 for j in picked):
        picked.append(int(i))
    if len(picked) >= 25:
        break
picked.sort(key=lambda i: ppm[i])
print("\ntop maxima >=5%% of max, >=0.05 ppm apart (%d):" % len(picked))
for i in picked:
    print("   ppm %8.4f  height %.4e  (rel %.3f)" % (ppm[i], spec[i], spec[i]/spec.max()))

json.dump({'SF': SF, 'CARRIER_PPM': CARRIER_PPM, 'SW_h': SW_h, 'dt': dt,
           'N': int(N), 'NFFT': NFFT, 'LB': LB, 'PHC0': PHC0, 'PHC1': PHC1,
           'targets': res,
           'picked': [[float(ppm[i]), float(spec[i]), float(spec[i]/spec.max())] for i in picked]},
          open(OUT + '/reference.json', 'w'), indent=1)
print("\nsaved", OUT + '/reference.json')
