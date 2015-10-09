from django import forms
import integralstor_common
import common_forms
from integralstor_common import networking

class EditHostnameForm(forms.Form):
  hostname = forms.CharField()
  domain_name = forms.CharField(required=False)

  def clean(self):
    cd = super(EditHostnameForm, self).clean()
    hostname = cd['hostname']
    if '.' in hostname:
      self._errors["hostname"] = self.error_class(["Please enter a hostname without the domain name component (no '.'s allowed)"])
    return cd

class DNSNameServersForm(forms.Form):

  nameservers = common_forms.MultipleServerField()

class NICForm(forms.Form):

  name = forms.CharField(widget=forms.HiddenInput)
  ip = forms.GenericIPAddressField(protocol='IPv4', required=False)
  netmask = forms.GenericIPAddressField(protocol='IPv4', required=False)
  default_gateway = forms.GenericIPAddressField(protocol='IPv4', required = False)
  ch = [('static', r'Static'), ('dhcp', r'DHCP')]
  addr_type = forms.ChoiceField(choices=ch, widget=forms.RadioSelect())

  def clean(self):
    cd = super(NICForm, self).clean()
    addr_type = cd['addr_type']
    if addr_type == 'static':
      if 'ip' not in cd or not cd['ip']:
        self._errors["ip"] = self.error_class(["IP address is required for static addressing"])
      if 'netmask' not in cd or not cd['netmask']:
        self._errors["ip"] = self.error_class(["Netmask is required for static addressing"])
      netmask = cd['netmask']
      valid, err = networking.validate_netmask(netmask)
      if not valid:
        self._errors["netmask"] = self.error_class(["Invalid netmask"])
    return cd

class CreateBondForm(forms.Form):

  name = forms.CharField()
  ch = [('4', r'802.3ad'), ('6', r'balance-alb')]
  mode =  forms.ChoiceField(widget=forms.Select, choices=ch)
  interfaces = None
  existing_bonds = None

  def __init__(self, *args, **kwargs):
    dsll = None
    if kwargs:
      self.interfaces = kwargs.pop('interfaces')
      self.existing_bonds = kwargs.pop('existing_bonds')
    super(CreateBondForm, self).__init__(*args, **kwargs)
    ch = []
    if self.interfaces:
      for iface in self.interfaces:
        tup = (iface, iface)
        ch.append(tup)   
    self.fields["slaves"] = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple(), choices=ch)

  def clean(self):
    cd = super(CreateBondForm, self).clean()
    name = cd['name']
    if name in self.existing_bonds:
      self._errors["name"] = self.error_class(["A bond or interface of this name already exists. Please choose another name."])
    return cd

class CreateRouteForm(forms.Form):

  type = forms.ChoiceField(widget=forms.Select,choices=[('default','default'),('static','static')],required=False)
  ip = forms.GenericIPAddressField(protocol='IPv4', required=True)
  netmask = forms.GenericIPAddressField(protocol='IPv4', required=True)
  gateway = forms.GenericIPAddressField(protocol='IPv4', required = True)
  
