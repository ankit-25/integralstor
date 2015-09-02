
import json,sqlite3

import integralstor_common
from integralstor_common import command, db, common

import local_users

import salt.client 


def change_auth_method(security):

  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    cl = []
    cl.append(["update samba_global_common set security='%s' where id=1"%security])
    cl.append(["delete from samba_valid_users"])
    db.execute_iud("%s/integral_view_config.db"%db_path, cl)
  except Exception, e:
    return False, 'Error changing authentication method : %s'%str(e)
  else:
    return True, None

def load_auth_settings():
  d = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = None
    d = db.read_single_row("%s/integral_view_config.db"%db_path, "select * from samba_global_common where id=1")
    if d and d["security"] == "ads":
      d1 = db.read_single_row("%s/integral_view_config.db"%db_path, "select * from samba_global_ad where id=1")
      if d1:
        d.update(d1)
  except Exception, e:
    return None, 'Error loading authentication settings: %s'%str(e)
  else:
    return d, None


def save_auth_settings(d):

  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    cmd_list = []
    cmd = ["update samba_global_common set workgroup=?, netbios_name=?, security=?, include_homes_section=? where id = ?", (d["workgroup"], d["netbios_name"], d["security"], True, 1,)]
    cmd_list.append(cmd)
    if d["security"] == "ads":
      d1 = db.read_single_row("%s/integral_view_config.db"%db_path, "select * from samba_global_ad")
      if d1:
        #cmd = ["update samba_global_ad set realm=?, password_server=?, ad_schema_mode=?, id_map_min=?, id_map_max=?  where id = ?", (d["realm"], d["password_server"], d["ad_schema_mode"], d["id_map_min"], d["id_map_max"], 1,)]
        cmd = ["update samba_global_ad set realm=?, password_server=?, ad_schema_mode=?, id_map_min=?, id_map_max=?, password_server_ip=?  where id = ?", (d["realm"], d["password_server"], 'rfc2307', 16777216, 33554431, d["password_server_ip"], 1, )]
        cmd_list.append(cmd)
      else:
        #cmd = ["insert into samba_global_ad (realm, password_server, ad_schema_mode, id_map_min, id_map_max, id) values(?,?,?,?,?,?)", (d["realm"], d["password_server"], d["ad_schema_mode"], d["id_map_min"], d["id_map_max"], 1,)]
        cmd = ["insert into samba_global_ad (realm, password_server, ad_schema_mode, id_map_min, id_map_max, password_server_ip, id) values(?,?,?,?,?,?,?)", (d["realm"], d["password_server"], 'rfc2307', 16777216, 33554431, d["password_server_ip"], 1,)]
        cmd_list.append(cmd)
    #print cmd_list
    #Always try to create the fractalio_guest account for guest access - will fail if it exists so ok
    ret, err = local_users.create_local_user('integralstor_guest', 'Integralstor Guest', 'integralstorguest')
    db.execute_iud("%s/integral_view_config.db"%db_path, cmd_list)
  except Exception, e:
    return False, 'Error saving authentication settings : %s'%str(e)
  else:
    return True, None


def delete_auth_settings():
  conn = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    cur = conn.cursor()
    cur.execute("delete from samba_auth ")
    cur.close()
    conn.commit()
  except Exception, e:
    return False, 'Error deleting authentication settings: %s'%str(e)
  else:
    return True, None
  finally:
    if conn:
      conn.close()

def load_shares_list():
  conn = None
  l = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("select * from samba_shares")
    rows = cur.fetchall()
    if rows:
      l = []
      for row in rows:
        d = {}
        for key in row.keys():
          d[key] = row[key]
        l.append(d)
  except Exception, e:
    return None, 'Error loading shares list: %s'%str(e)
  else:
    return l, None
  finally:
    if conn:
      conn.close()

def load_share_info(mode, index):
  d = None
  conn = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if mode == "by_id":
      cur.execute("select * from samba_shares where share_id = %s"%index)
    else:
      cur.execute("select * from samba_shares where name = %s"%index)
    r = cur.fetchone()
    if not r:
      return None
    d = {}
    if not r:
      raise Exception('Specified share not found')
    for key in r.keys():
      d[key] = r[key]
  except Exception, e:
    return None, 'Error loading share information : %s'%str(e)
  else:
    return d, None
  finally:
    if conn:
      conn.close()


def delete_share(share_id):

  conn = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    cur = conn.cursor()
    cur.execute("delete from samba_shares where share_id=?", (share_id, ))
    cur.execute("delete from samba_valid_users where share_id=?", (share_id, ))
    cur.close()
    conn.commit()
  except Exception, e:
    return False, 'Error deleting share : %s'%str(e)
  else:
    return True, None
  finally:
    if conn:
      conn.close()

def delete_all_shares():
  conn = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    cur = conn.cursor()
    cur.execute("delete from samba_shares ")
    cur.execute("delete from samba_valid_users ")
    cur.close()
    conn.commit()
  except Exception, e:
    return False, 'Error deleting all shares: %s'%str(e)
  else:
    return True, None
  finally:
    if conn:
      conn.close()

def save_share(share_id, name, comment, guest_ok, read_only, path, browseable, users, groups):

  conn = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    cur = conn.cursor()
    cur.execute("update samba_shares set comment=?, read_only=?, guest_ok=?, browseable=? where share_id=?", (comment, read_only, guest_ok, browseable,share_id, ))
    cur.execute("delete from samba_valid_users where share_id=?", (share_id, ))
    
    if not guest_ok:
      if users:
        for user in users:
          cur.execute("insert into samba_valid_users (id, share_id, grp, name) values (NULL,?,?,?)", (share_id, False, user,))
      if groups:
        for group in groups:
          cur.execute("insert into samba_valid_users (id, share_id, grp, name) values (NULL,?,?,?)", (share_id, True, group,))
    cur.close()
    conn.commit()
  except Exception, e:
    return False, 'Error saving share : %s'%str(e)
  else:
    return True, None
  finally:
    if conn:
      conn.close()


def create_share(name, comment, guest_ok, read_only, path, display_path, browseable, users, groups, vol):
  conn = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    d, err = load_auth_settings()
    if err:
      raise Exception(err)
    if not d:
      raise Exception("Authentication settings not set. Please set authentication settings before creating shares.")
    shl, err = load_shares_list()
    if err:
      raise Exception(err)
    if shl:
      for sh in shl:
        if sh["name"] == name :
          raise Exception("A share with that name already exists")
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    cur = conn.cursor()
    cur.execute("insert into samba_shares (name, vol, path, display_path, comment, read_only, guest_ok, browseable, share_id) values (?,?, ?,?,?,?,?,?,NULL)", (name, vol, path, display_path, comment, read_only, guest_ok, browseable,))
    share_id = cur.lastrowid
    if not guest_ok:
      if users:
        for user in users:
          cur.execute("insert into samba_valid_users (id, share_id, grp, name) values (NULL,?,?,?)", (share_id, False, user,))
      if groups:
        for group in groups:
          cur.execute("insert into samba_valid_users (id, share_id, grp, name) values (NULL,?,?,?)", (share_id, True, group,))
    cur.close()
    conn.commit()
  except Exception, e:
    return False, 'Error creating share: %s'%str(e)
  else:
    return True, None
  finally:
    if conn:
      conn.close()

def _generate_global_section(f, d):
  try:
    f.write("; This file has been programatically generated by the fractal view system. Do not modify it manually!\n\n")
    f.write("[global]\n")
    f.write("  server string = Integralstor Unicell File server\n")
    f.write("  log file = /var/log/smblog.vfs\n")
    #f.write("  log level=5\n")
    f.write("  log level=1 acls:3 locking:3\n")
    f.write("  oplocks=yes\n")
    f.write("  ea support=yes\n")
    f.write("  level2 oplocks=yes\n")
    f.write("  posix locking=no\n")
    f.write("  load printers = no\n")
    f.write("  map to guest = bad user\n")
    f.write("  idmap config *:backend = tdb\n")
    f.write("  workgroup = %s\n"%d["workgroup"].upper())
    f.write("  netbios name = %s\n"%d["netbios_name"].upper())
    if d["security"] == "ads":
      f.write("  security = ADS\n")
      f.write("  preferred master = no\n")
      f.write("  encrypt passwords = yes\n")
      f.write("  winbind enum users  = yes\n")
      f.write("  winbind enum groups = yes\n")
      f.write("  winbind use default domain = yes\n")
      f.write("  winbind nested groups = yes\n")
      f.write("  winbind separator = +\n")
      f.write("  local master = no\n")
      f.write("  domain master = no\n")
      f.write("  wins proxy = no\n")
      f.write("  dns proxy = no\n")
      #f.write("  idmap config *:range = %d-%d \n"%(d["id_map_max"]+1, d["id_map_max"]+10001))
      f.write("  winbind nss info = rfc2307\n")
      f.write("  winbind trusted domains only = no\n")
      f.write("  winbind refresh tickets = yes\n")
      f.write("  map untrusted to domain = Yes\n")
      f.write("  realm = %s\n"%d["realm"].upper())
      f.write("  idmap config %s:default = yes\n"%d["workgroup"].upper())
      f.write("  idmap config %s:backend = ad\n"%d["workgroup"].upper())
      f.write("  idmap config %s:schema_mode = %s\n"%(d["workgroup"].upper(), d["ad_schema_mode"]))
      #f.write("  idmap config %s:range = %d-%d\n"%(d["workgroup"].upper(), d["id_map_min"], d["id_map_max"]))
      f.write("  idmap config %s:range = 16777216-33554431\n")
      f.write("  idmap config %s:base_rid = 0\n"%d["workgroup"].upper())
  except Exception, e:
    return False, 'Error generating CIFS config - global section : %s'%str(e)
  else:
    return True, None

def _generate_share_section(f, share_name, vol_name, workgroup, path, read_only, browseable, guest_ok, user_list, group_list, comment, auth_method):
  try:
    f.write("\n[%s]\n"%share_name)
    if comment:
      f.write("  comment = %s\n"%comment)
    f.write("  path = %s\n"%path)
    f.write("  create mask = 0660\n")
    f.write("  kernel share modes = no\n")
    f.write("  directory mask = 0770\n")
    if read_only:
      t = "yes"
    else:
      t = "no"
    f.write("  read only = %s\n"%t)
    if user_list or group_list:
      s = "  valid users = "
      for user in user_list:
        if auth_method and auth_method == "users":
          s += " %s "%(user)
        else:
          s += " %s+%s "%(workgroup, user)
      for group in group_list:
        if auth_method and auth_method == "users":
          s += " @%s "%(group)
        else:
          s += " @%s+%s "%(workgroup, group)
      s += "\n"
      f.write(s)

    if browseable:
      t = "yes"
    else:
      t = "no"
    f.write("  browseable = %s\n"%t)
    if guest_ok:
      f.write("  guest ok = yes\n")
      #f.write("  guest account = %s\n"%guest_account)
  except Exception, e:
    return False, 'Error generating CIFS config - share section: %s'%str(e)
  else:
    return True, None
    
def generate_smb_conf():
  try:
    d, err = load_auth_settings()
    if err:
      raise Exception(err)
    smb_conf_path, err = common.get_smb_conf_path()
    if err:
      raise Exception(err)
    with open("%s/smb.conf"%smb_conf_path, "w+") as f:
      ret, err = _generate_global_section(f, d)
      if err:
        raise Exception(err)
      shl, err = load_shares_list()
      if err:
        raise Exception(err)
      if shl:
        for share in shl:
          ul = []
          gl = []
          if not share["guest_ok"]:
            vul, err = load_valid_users_list(share["share_id"])
            if err:
              raise Exception(err)
            if vul:
              for vu in vul:
                if vu["grp"]:
                  gl.append(vu["name"])
                else:
                  ul.append(vu["name"])
          ret, err = _generate_share_section(f, share["name"], share["vol"], d["workgroup"], share["path"], share["read_only"], share["browseable"], share["guest_ok"], ul, gl, share["comment"], d["security"])
          if err:
            raise Exception(err)
    f.close()
    ret, errors = _reload_config()
    if errors:
      raise Exception(errors)
  except Exception, e:
    return False, 'Error generating CIFS config : %s'%str(e)
  else:
    return True, None

def _reload_config():
  try:
    use_salt, err = common.use_salt()
    if err:
      raise Exception(err)
    if use_salt:
      errors = ''
      client = salt.client.LocalClient()
      r1 = client.cmd('*', 'cmd.run_all', ['smbcontrol all reload-config'])
      if r1:
        for node, ret in r1.items():
          #print ret
          if ret["retcode"] != 0:
            errors += "Error reloading samba on node %s "%node
      if errors:
        raise Exception(errors)
    else:
      cmd_to_run = 'smbcontrol all reload-config'
      (ret, rc), err = command.execute_with_rc(cmd_to_run)
      if err:
        raise Exception(err)
      if rc != 0:
        err = ''
        tl, er = command.get_output_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = ','.join(tl)
        tl, er = command.get_error_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = err + ','.join(tl)
        raise Exception("Return code : %d. Error : %s"%(rc, err))
  except Exception, e:
    return False, 'Error reloading CIFS configuration : %s'%str(e)
  else:
    return True, None

def generate_krb5_conf():
  try:
    d, err = load_auth_settings()
    if err:
      raise Exception(err)
    krb5_conf_path, err = common.get_krb5_conf_path()
    if err:
      raise Exception(err)
    with open("%s/krb5.conf"%krb5_conf_path, "w") as f:
      f.write("; This file has been programatically generated by the fractal view system. Do not modify it manually!\n\n")
      f.write("[logging]\n")
      f.write("  default = FILE:/var/log/krb5libs.log\n")
      f.write("  kdc = FILE:/var/log/krb5kdc.log\n")
      f.write("  admin_server = FILE:/var/log/kadmind.log\n")
  
      f.write("\n[libdefaults]\n")
      f.write("  default_realm = %s\n"%d["realm"].upper())
      f.write("\n[realms]\n")
      f.write("    %s = {\n"%d["realm"].upper())
      f.write("    kdc = %s\n"%d["password_server"])
      f.write("    admin_server = %s\n"%d["password_server"])
      f.write("  }\n")
      f.write("\n[domain_realm]\n")
      f.write("  .%s = %s\n"%(d["realm"].lower(), d["realm"].upper()))
      f.write("  %s = %s\n"%(d["realm"].lower(), d["realm"].upper()))
    f.close()
  except Exception, e:
    return False, 'Error generating kerberos config: %s'%str(e)
  else:
    return True, None

def kinit(user, pswd, realm):
  try:
    cmd_to_run = 'echo "%s\n" | kinit %s@%s'%(pswd, user, realm)
    use_salt, err = common.use_salt()
    if err:
      raise Exception(err)
    if use_salt:
      errors = []
      client = salt.client.LocalClient()
      print 'Running %s'%cmd_to_run
      #assert False
      r1 = client.cmd('*', 'cmd.run_all', [cmd_to_run])
      if r1:
        for node, ret in r1.items():
          #print ret
          if ret["retcode"] != 0:
            e = "Error initiating kerberos on GRIDCell %s"%node
            if "stderr" in ret:
              e += " : %s"%ret["stderr"]
            errors.append(e)
            print errors
      print r1
      if errors:
        raise Exception(' '.join(errors))
    else:
      (ret, rc), err = command.execute_with_rc(cmd_to_run)
      if err:
        raise Exception(err)
      if rc != 0:
        err = ''
        tl, er = command.get_output_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = ','.join(tl)
        tl, er = command.get_error_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = err + ','.join(tl)
        raise Exception("Return code : %d. Error : %s"%(rc, err))
  except Exception, e:
    return False, 'Error initing kerberos : %s'%str(e)
  else:
    return True, None

def net_ads_join(user, pswd, password_server):
  try:
    cmd_to_run = "net ads join -S %s  -U %s%%%s"%(password_server, user, pswd)
    use_salt, err = common.use_salt()
    if err:
      raise Exception(err)
    if use_salt:
      errors = []
      client = salt.client.LocalClient()
      print 'Running %s'%cmd_to_run
      #assert False
      r1 = client.cmd('*', 'cmd.run_all', [cmd_to_run])
      print r1
      if r1:
        for node, ret in r1.items():
          #print ret
          if ret["retcode"] != 0:
            e = "Error joining AD on node %s"%node
            if "stderr" in ret:
              e += " : %s"%ret["stderr"]
            errors.append(e)
            print errors
      print r1
      if errors:
        raise Exception(' '.join(errors))
    else:
      (ret, rc), err = command.execute_with_rc(cmd_to_run)
      if err:
        raise Exception(err)
      if rc != 0:
        err = ''
        tl, er = command.get_output_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = ','.join(tl)
        tl, er = command.get_error_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = err + ','.join(tl)
        raise Exception("Return code : %d. Error : %s"%(rc, err))
  except Exception, e:
    return False , 'Error joining AD: %s'%str(e)
  else:
    return True, None

def restart_samba_services():
  try:
    use_salt, err = common.use_salt()
    if err:
      raise Exception(err)
    if use_salt:
      client = salt.client.LocalClient()
      rc = client.cmd('*', 'service.reload', ['smbd'] )
      print rc
      rc = client.cmd('*', 'service.restart', ['winbind'] )
      print rc
      #rc = client.cmd('*', 'service.restart', ['nmbd'] )
      #print rc
    else:
      (ret, rc), err = command.execute_with_rc('service smbd reload')
      if err:
        raise Exception(err)
      (ret, rc), err = command.execute_with_rc('service winbind restart')
      if err:
        raise Exception(err)
      if rc != 0:
        err = ''
        tl, er = command.get_output_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = ','.join(tl)
        tl, er = command.get_error_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = err + ','.join(tl)
        raise Exception("Return code : %d. Error : %s"%(rc, err))
      (ret, rc), err = command.execute_with_rc('service nmbd restart')
      if err:
        raise Exception(err)
      if rc != 0:
        err = ''
        tl, er = command.get_output_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = ','.join(tl)
        tl, er = command.get_error_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = err + ','.join(tl)
        raise Exception("Return code : %d. Error : %s"%(rc, err))
  except Exception, e:
    return False, 'Error restarting samba services: %s'%str(e)
  else:
    return True, None

def _get_user_or_group_list(type):
  ret = None
  try:
    d, err = load_auth_settings()
    if err:
      raise Exception(err)
    if not d:
      raise Exception("Unspecified authentication method. Could not retrieve users")
    elif d["security"] == "users":
      if type and type == "users":
        l, err = local_users.get_local_users()
        if err:
          raise Exception(err)
        if l:
          rl = []
          for ld in l:
            rl.append(ld["username"])
          ret = rl
        else:
          ret = None
      else:
        l, err = local_users.get_local_groups()
        if err:
          raise Exception(err)
        if l:
          rl = []
          for ld in l:
            rl.append(ld["grpname"])
          ret = rl
        else:
          ret = None
    elif d["security"] == "ads":
      if type and type == "users":
        ret, err =  _get_ad_users_or_groups("users")
        if err:
          raise Exception(err)
      elif type and type == "groups":
        ret, err =  _get_ad_users_or_groups("groups")
        if err:
          raise Exception(err)
    else:
      raise Exception("Unsupported authentication method. Could not retrieve users")
  except Exception, e:
    return None, 'Error retrieving user of group list : %s'%str(e)
  else:
    return ret, None

def get_user_list():
  ret, err = _get_user_or_group_list("users")
  return ret, err

def get_group_list():
  ret, err =  _get_user_or_group_list("groups")
  return ret, err

def load_valid_users_list(share_id):
  l = None
  conn = None
  try:
    db_path, err = common.get_db_path()
    if err:
      raise Exception(err)
    conn = sqlite3.connect("%s/integral_view_config.db"%db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("select * from samba_valid_users where share_id = %s"%share_id)
    rows = cur.fetchall()
    if rows:
      l = []
      for row in rows:
        d = {}
        for key in row.keys():
          d[key] = row[key]
        l.append(d)
  except Exception, e:
    return None, 'Error loading valid users list : %s'%str(e)
  else:
    return l, None
  finally:
    if conn:
      conn.close()


def _get_ad_users_or_groups(type):
  o = None
  try:
    d, err = load_auth_settings()
    if err:
      raise Exception(err)
    workgroup = d['workgroup']
    if type and type=="users":
      (ret, rc), err = command.execute_with_rc("wbinfo -u --domain=%s"%workgroup)
      if err:
        raise Exception(err)
      if rc != 0:
        err = ''
        tl, er = command.get_output_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = ','.join(tl)
        tl, er = command.get_error_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = err + ','.join(tl)
        raise Exception("Return code : %d. Error : %s"%(rc, err))

    elif type and type=="groups":
      (ret, rc), err = command.execute_with_rc("wbinfo -g --domain=%s"%workgroup)
      if err:
        raise Exception(err)
      if rc != 0:
        err = ''
        tl, er = command.get_output_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = ','.join(tl)
        tl, er = command.get_error_list(ret)
        if er:
          raise Exception(er)
        if tl:
          err = err + ','.join(tl)
        raise Exception("Return code : %d. Error : %s"%(rc, err))
    else:
      raise Exception("Unknown type specified.")

    o, err = command.get_output_list(ret[0])
    if err:
      raise Exception(err)
    #print "wbinfo output = "
    #print o
    e, err = command.get_error_list(ret[0])
    if err:
      raise Exception(err)
    #print "error = "
    #print e
    if ret[1] != 0:
      err = ""
      if o:
        err += " ".join(o)
        err += ". "
      if e:
        err += " ".join(e)
      raise Exception(err)
  except Exception, e:
    return None, 'Error retrieving Active Directory Users/Groups : %s'%str(e)
  else:
    return o, None

def main():
  generate_krb5_conf()

if __name__ == "__main__":
  main()
