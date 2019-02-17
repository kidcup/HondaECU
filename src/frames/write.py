import wx
import os
import time
import tarfile
import json
from .base import HondaECU_AppPanel
from pydispatch import dispatcher

from ecu import *

class HondaECU_WritePanel(HondaECU_AppPanel):

	def Build(self):
		if self.parent.nobins:
			self.wildcard = "HondaECU tune file (*.htf)|*.htf"
		else:
			self.wildcard = "HondaECU supported files (*.htf,*.bin)|*.htf;*.bin|HondaECU tune file (*.htf)|*.htf|ECU dump (*.bin)|*.bin"
		self.byts = None
		self.statusbar = self.CreateStatusBar(1)
		self.statusbar.SetSize((-1, 28))
		self.statusbar.SetStatusStyles([wx.SB_SUNKEN])
		self.SetStatusBar(self.statusbar)

		self.outerp = wx.Panel(self)
		self.writep = wx.Panel(self.outerp)
		self.wfilel = wx.StaticText(self.writep, label="File")
		self.writefpicker = wx.FilePickerCtrl(self.writep,wildcard=self.wildcard, style=wx.FLP_OPEN|wx.FLP_FILE_MUST_EXIST|wx.FLP_USE_TEXTCTRL|wx.FLP_SMALL)
		self.optsp = wx.Panel(self.writep)
		self.wchecksuml = wx.StaticText(self.optsp,label="Checksum Location")
		self.fixchecksum = wx.CheckBox(self.optsp, label="Fix")
		self.checksum = wx.TextCtrl(self.optsp)
		self.offsetl = wx.StaticText(self.optsp,label="Start Offset")
		self.offset = wx.TextCtrl(self.optsp)
		self.offset.SetValue("0x0")
		self.htfoffset = None

		self.gobutton = wx.Button(self.writep, label="Start")
		self.gobutton.Disable()
		self.checksum.Disable()

		self.optsbox = wx.BoxSizer(wx.HORIZONTAL)
		self.optsbox.Add(self.offsetl, 0, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, border=10)
		self.optsbox.Add(self.offset, 0)
		self.optsbox.Add(self.wchecksuml, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, border=10)
		self.optsbox.Add(self.checksum, 0)
		self.optsbox.Add(self.fixchecksum, 0, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, border=10)
		self.optsp.SetSizer(self.optsbox)

		self.fpickerbox = wx.BoxSizer(wx.HORIZONTAL)
		self.fpickerbox.Add(self.writefpicker, 1)

		self.lastpulse = time.time()
		self.progress = wx.Gauge(self.writep, size=(400,-1), style=wx.GA_HORIZONTAL|wx.GA_SMOOTH)
		self.progress.SetRange(100)

		self.flashpsizer = wx.GridBagSizer()
		self.flashpsizer.Add(self.wfilel, pos=(0,0), flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, border=10)
		self.flashpsizer.Add(self.fpickerbox, pos=(0,1), span=(1,5), flag=wx.EXPAND|wx.RIGHT|wx.BOTTOM, border=10)
		self.flashpsizer.Add(self.optsp, pos=(1,0), span=(1,6), flag=wx.BOTTOM, border=20)
		self.flashpsizer.Add(self.progress, pos=(2,0), span=(1,6), flag=wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.EXPAND, border=20)
		self.flashpsizer.Add(self.gobutton, pos=(3,5), flag=wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.RIGHT, border=10)
		self.flashpsizer.AddGrowableRow(3,1)
		self.flashpsizer.AddGrowableCol(5,1)
		self.writep.SetSizer(self.flashpsizer)

		self.outersizer = wx.BoxSizer(wx.VERTICAL)
		self.outersizer.Add(self.writep, 1, wx.EXPAND|wx.ALL, border=10)
		self.outerp.SetSizer(self.outersizer)

		self.mainsizer = wx.BoxSizer(wx.VERTICAL)
		self.mainsizer.Add(self.outerp, 1, wx.EXPAND)
		self.SetSizer(self.mainsizer)

		self.Layout()
		self.mainsizer.Fit(self)

		self.offset.Bind(wx.EVT_TEXT, self.OnValidateMode)
		self.writefpicker.Bind(wx.EVT_FILEPICKER_CHANGED, self.OnFileSelected)
		self.fixchecksum.Bind(wx.EVT_CHECKBOX, self.OnFix)
		self.checksum.Bind(wx.EVT_TEXT, self.OnValidateMode)
		self.gobutton.Bind(wx.EVT_BUTTON, self.OnGo)
		self.optsp.Hide()

	def OnFileSelected(self, event):
		self.htfoffset = None
		if len(self.writefpicker.GetPath()) > 0 and os.path.splitext(self.writefpicker.GetPath())[-1] == ".htf":
			self.optsp.Hide()
			self.doHTF = True
		else:
			self.optsp.Show()
			self.doHTF = False
		self.OnValidateMode(event)

	def OnValidateMode(self, event):
		if self.doHTF:
			self.OnValidateModeHTF(event)
		else:
			self.OnValidateModeBin(event)
		self.Layout()

	def OnFix(self, event):
		if self.fixchecksum.IsChecked():
			self.checksum.Enable()
		else:
			self.checksum.Disable()
		self.OnValidateMode(None)

	def KlineWorkerHandler(self, info, value):
		if info == "progress":
			if value[0]!= None and value[0] >= 0:
				self.progress.SetValue(value[0])
				self.statusbar.SetStatusText("Write: " + value[1], 0)
		elif info == "write.result":
			self.progress.SetValue(0)
			self.statusbar.SetStatusText("Write complete (result=%s)" % value, 0)

	def OnGo(self, event):
		if self.htfoffset != None:
			offset = int(self.htfoffset, 16)
		else:
			offset = int(self.offset.GetValue(), 16)
		self.gobutton.Disable()
		dispatcher.send(signal="WritePanel", sender=self, data=self.byts, offset=offset)

	def OnValidateModeHTF(self, event):
		if len(self.writefpicker.GetPath()) > 0:
			if os.path.isfile(self.writefpicker.GetPath()):
				tar = tarfile.open(self.writefpicker.GetPath(), "r:xz")
				binmod = None
				metainfo = None
				for f in tar.getnames():
					if f == "metainfo.json":
						metainfo = json.load(tar.extractfile(f))
					else:
						b,e = os.path.splitext(f)
						if e == ".bin":
							x, y = os.path.splitext(b)
							if y == ".mod":
								binmod = bytearray(tar.extractfile(f).read())
				if binmod != None and metainfo != None:
					ea = int(metainfo["ecmidaddr"],16)
					ka = int(metainfo["keihinaddr"],16)
					if "offset" in metainfo:
						self.htfoffset = metainfo["offset"]
					if "rid" in metainfo and metainfo["rid"] != None:
						for i in range(5):
							binmod[ea+i] ^= 0xFF
						for i in range(7):
							binmod[ka+i] = ord(metainfo["rid"][i])
					ret, status, self.byts = do_validation(binmod, len(binmod), int(metainfo["checksum"],16))
					if status != "bad":
						self.gobutton.Enable()
						return
		self.gobutton.Disable()

	def OnValidateModeBin(self, event):
		offset = None
		try:
			offset = int(self.offset.GetValue(), 16)
		except:
			self.gobutton.Disable()
			return
		checksum = None
		try:
			if self.fixchecksum.IsChecked():
				checksum = int(self.checksum.GetValue(), 16)
			else:
				checksum = 0
		except:
			self.gobutton.Disable()
			return
		if len(self.writefpicker.GetPath()) > 0:
			if os.path.isfile(self.writefpicker.GetPath()):
				fbin = open(self.writefpicker.GetPath(), "rb")
				nbyts = os.path.getsize(self.writefpicker.GetPath())
				byts = bytearray(fbin.read(nbyts))
				fbin.close()
				if checksum >= nbyts:
					self.gobutton.Disable()
					return
				ret, status, self.byts = do_validation(byts, nbyts, checksum)
				if status != "bad":
					self.gobutton.Enable()
					return
		self.gobutton.Disable()
