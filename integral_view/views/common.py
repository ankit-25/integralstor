import json, time, os, shutil, tempfile, os.path, re, subprocess, sys, shutil, pwd, grp, stat,datetime

import salt.client, salt.wheel

import django.template, django
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


import integralstor_common
from integralstor_common import command, db, common, audit, alerts, mail, zfs, file_processing,stats,scheduler_utils,common
from integralstor_common import cifs as cifs_common, services_management

import integralstor_unicell
from integralstor_unicell import system_info, local_users

from integral_view.utils import iv_logging


production = common.is_production()

def dir_contents(request):
  path = request.GET.get("pool_name")
  first = request.GET.get("first")
  dirs = os.listdir(path)
  dir_dict_list = []
  if not dirs or first:
    d_dict = {'id':path, 'text':"/",'icon':'fa fa-angle-right','children':True,'data':{'dir':path},'parent':"#"}
    dir_dict_list.append(d_dict)
  if not first:
    for d in dirs:
      true = True
      if os.path.isdir(path+"/"+d):
        if first:
          parent = "#"
        else:
          parent = path
        d_dict = {'id':path+"/"+d, 'text':d,'icon':'fa fa-angle-right','children':True,'data':{'dir':path+"/"+d},'parent':parent}
      dir_dict_list.append(d_dict)
  return HttpResponse(json.dumps(dir_dict_list),mimetype='application/json')


@login_required
def dashboard(request,page):
  return_dict = {}
  try:
    if request.method != 'GET':
      raise Exception('Invalid access method. Please use the menus')
    si, err = system_info.load_system_config()
    if err:
      raise Exception(err)
    if not si:
      raise Exception('Error loading system configuration')
    return_dict['system_info'] = si
    #By default show error page
    template = "logged_in_error.html"
    num_nodes_bad = 0
    total_pool = 0
    total_nodes = len(si)
    nodes = {}
    # Chart specific declarations
    today_day = (datetime.date.today()).strftime('%d') # will return 02, instead of 2.
    # This is a hack, need to figure out a better way to get hour and minute in 2 digit format like today_day.
    start_hour = datetime.datetime.today().hour-3
    end_hour = datetime.datetime.today().hour
    if start_hour < 10:
      start_hour = '0%d'%start_hour
    if end_hour < 10:
      end_hour = '0%d'%end_hour
    minute = datetime.datetime.today().minute
    if minute < 10:
      minute = '0%d'%minute
    start = str(start_hour)+":"+str(minute)+str(":10")
    end = str(end_hour)+":"+str(minute)+str(":40")
    #today_day = datetime.datetime.today().day
    #if end < 10:
    #  end = '0%d'%end
    value_list = []
    time_list = []
    use_salt, err = common.use_salt()
    if err:
      raise Exception(err)
        
    ks = si.keys()
    if not ks:
      raise Exception('System configuration invalid')
    info = ks[0]
    # CPU status
    if page == "cpu":
      return_dict["page_title"] = 'CPU statistics'
      return_dict['tab'] = 'cpu_tab'
      return_dict["error"] = 'Error loading CPU statistics'
      cpu,err = stats.get_system_stats(today_day,start,end,"cpu")
      if err:
        raise Exception(err)
      value_dict = {}
      if cpu:
        for key in cpu.keys():
          value_list = []
          time_list = []
          if key == "date":
            pass
          else:
            if cpu[key]:
              for a in cpu[key]:
                time_list.append(a[0])
                value_list.append(a[1])
            value_dict[key] = value_list
      return_dict["data_dict"] = value_dict
      queue,err = stats.get_system_stats(today_day,start,end,"queue")
      if err:
        raise Exception(err)
      value_dict = {}
      if queue:
        for key in queue.keys():
          value_list = []
          time_list = []
          if key == "date":
            pass
          else:
            for a in queue[key]:
              time_list.append(a[0])
              value_list.append(a[1])
            value_dict[key] = value_list
      return_dict["data_dict_queue"] = value_dict
      return_dict['node_name'] = info
      return_dict['node'] = si[info]
      d = {}
      template = "view_cpu_status.html"
    # Hardware
    elif page == "hardware":
      return_dict["page_title"] = 'Hardware status'
      return_dict['tab'] = 'hardware_tab'
      return_dict["error"] = 'Error loading hardware status'
      d = {}
      d['ipmi_status'] = si[info]['ipmi_status']
      return_dict['hardware_status'] =  d
      return_dict['node_name'] = info
      template = "view_hardware_status.html"
    # Memory
    elif page == "memory":
      return_dict["page_title"] = 'Memory statistics'
      return_dict['tab'] = 'memory_tab'
      return_dict["error"] = 'Error loading memory statistics'
      mem,err = stats.get_system_stats(today_day,start,end,"memory")
      if err:
        raise Exception(err)
      if mem:
        for a in mem["memused"]:
          time_list.append(a[0])
          value_list.append((a[1]/(1024*1024)))
      return_dict['memory_status'] =  si[info]['memory']
      template = "view_memory_status.html"
    # Network
    elif page == "network":
      return_dict["page_title"] = 'Network statistics'
      return_dict['tab'] = 'network_tab'
      return_dict["error"] = 'Error loading Network statistics'
      network,err = stats.get_system_stats(today_day,start,end,"network")
      if err:
        raise Exception(err)
      value_dict = {}
      if network:
        for key in network.keys():
          value_list = []
          time_list = []
          if key == "date" or key == "lo":
            pass
          else:
            for a in network[key]["ifutil-percent"]:
              time_list.append(a[0])
              value_list.append(a[1])
            value_dict[key] = value_list
          
      return_dict["data_dict"] = value_dict
      return_dict["network_status"] = si[info]['interfaces']
      template = "view_network_status.html"
    # Services
    elif page == "services":
      return_dict["page_title"] = 'System services status'
      return_dict['tab'] = 'services_tab'
      return_dict["error"] = 'Error loading system services status'
      return_dict['services_status'] = {}
      if use_salt:
        import salt.client
        client = salt.client.LocalClient()
        winbind = client.cmd(info,'cmd.run',['service winbind status'])
        smb = client.cmd(info,'cmd.run',['service smb status'])
        nfs = client.cmd(info,'cmd.run',['service nfs status'])
        iscsi = client.cmd(info,'cmd.run',['service tgtd status'])
        ntp = client.cmd(info,'cmd.run',['service ntpd status'])
        ftp = client.cmd(info,'cmd.run',['service vsftpd status'])
        return_dict['services_status']['winbind'] = winbind[info]
        return_dict['services_status']['smb'] = smb[info]
        return_dict['services_status']['nfs'] = nfs[info]
        return_dict['services_status']['iscsi'] = iscsi[info]
        return_dict['services_status']['ntp'] = ntp[info]
        return_dict['services_status']['ftp'] = ftp[info]
      else:
        out_list, err = command.get_command_output('service winbind status', False)
        if err:
          raise Exception(err)
        if out_list:
          return_dict['services_status']['winbind'] = ' '.join(out_list)
  
        out_list, err = command.get_command_output('service smb status', False)
        if err:
          raise Exception(err)
        if out_list:
          return_dict['services_status']['smb'] = ' '.join(out_list)
  
        out_list, err = command.get_command_output('service nfs status', False)
        if err:
          raise Exception(err)
        if out_list:
          return_dict['services_status']['nfs'] = ' '.join(out_list)
  
        out_list, err = command.get_command_output('service tgtd status', False)
        if err:
          raise Exception(err)
        if out_list:
          return_dict['services_status']['iscsi'] = ' '.join(out_list)
  
        out_list, err = command.get_command_output('service ntpd status', False)
        if err:
          raise Exception(err)
        if out_list:
          return_dict['services_status']['ntp'] = ' '.join(out_list)

        out_list, err = command.get_command_output('service vsftpd status', False)
        if err:
          raise Exception(err)
        if out_list:
          return_dict['services_status']['ftp'] = ' '.join(out_list)
          
      template = "view_services_status.html"
    # Disks
    elif page == "disks":
      return_dict["page_title"] = 'Hard drives status'
      return_dict['tab'] = 'disk_tab'
      return_dict["error"] = 'Error loading hard drives status'
      platform,err = common.get_hardware_platform()
      if not err:
        return_dict['hardware'] = platform
      return_dict['node'] = si[info]
      return_dict["disk_status"] = si[info]['disks']
      #print si[info]['disks']
      return_dict['node_name'] = info
      template = "view_disks_status.html"
    # Pools
    elif page == "pools":
      return_dict["page_title"] = 'ZFS pools status'
      return_dict['tab'] = 'pools_tab'
      return_dict["error"] = 'Error loading ZFS pools status'
      pools, err = zfs.get_pools()
      if err:
        raise Exception(err)
      if pools:
        return_dict['pools'] = pools            
      template = "view_pools_status.html"
    return_dict["labels"] = time_list
    return_dict["data"] = value_list
    return django.shortcuts.render_to_response(template, return_dict, context_instance=django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "dashboard_base.html"
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

  
@login_required    
def show(request, page, info = None):

  return_dict = {}
  try:

    si,err = system_info.load_system_config()
    if err:
      raise Exception(err)

    #assert False
    return_dict['system_info'] = si

    #By default show error page
    template = "logged_in_error.html"

    if page == "dir_contents":
      #CHANGE THIS TO SHOW LOCAL DIR LISTINGS!!
      return django.http.HttpResponse(dir_list,mimetype='application/json')

    elif page == "integral_view_log_level":

      template = "view_integral_view_log_level.html"
      try:
        log_level = iv_logging.get_log_level_str()
      except Exception, e:
        return_dict["error"] = str(e)
      else:
        return_dict["log_level_str"] = log_level
      if "saved" in request.REQUEST:
        return_dict["saved"] = request.REQUEST["saved"]

    '''
    elif page == "node_info":
      return_dict['base_template'] = "system_base.html"
      return_dict["page_title"] = 'System configuration'
      return_dict['tab'] = 'node_info_tab'
      return_dict["error"] = 'Error loading system configuration'
      template = "view_node_info.html"
      if "from" in request.GET:
        frm = request.GET["from"]
        return_dict['frm'] = frm
      #return_dict['node'] = si[info]
      return_dict['node'] = si[si.keys()[0]]
    '''


    return django.shortcuts.render_to_response(template, return_dict, context_instance=django.template.context.RequestContext(request))
  except Exception, e:
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))




'''
This functionality is now in zfs_management so this is to be deprecated!!

@login_required    
def set_file_owner_and_permissions(request):
  return_dict = {}
  try:
    if 'path' not in request.REQUEST:
      raise Exception('Path not specified')
    path = request.REQUEST['path']

    users, err = local_users.get_local_users()
    if err:
      raise Exception('Error retrieving local user list : %s'%err)
    if not users:
      raise Exception('No local users seem to be created. Please create at least one local user before performing this operation.')

    groups, err = local_users.get_local_groups()
    if err:
      raise Exception('Error retrieving local group list : %s'%err)
    if not groups:
      raise Exception('No local groups seem to be created. Please create at least one local group before performing this operation.')

    try:
      stat_info = os.stat(path)
    except Exception, e:
      raise Exception('Error accessing specified path : %s'%str(e))
    uid = stat_info.st_uid
    gid = stat_info.st_gid
    username = pwd.getpwuid(uid)[0]
    grpname = grp.getgrgid(gid)[0]
    return_dict["username"] = username
    return_dict["grpname"] = grpname


    if request.method == "GET":
      # Shd be an edit request
  
      # Set initial form values
      initial = {}
      initial['path'] = path
      initial['owner_read'] = _owner_readable(stat_info)
      initial['owner_write'] = _owner_writeable(stat_info)
      initial['owner_execute'] = _owner_executeable(stat_info)
      initial['group_read'] = _group_readable(stat_info)
      initial['group_write'] = _group_writeable(stat_info)
      initial['group_execute'] = _group_executeable(stat_info)
      initial['other_read'] = _other_readable(stat_info)
      initial['other_write'] = _other_writeable(stat_info)
      initial['other_execute'] = _other_executeable(stat_info)
  
      form = common_forms.SetFileOwnerAndPermissionsForm(initial = initial, user_list = users, group_list = groups)
  
      return_dict["form"] = form
      return django.shortcuts.render_to_response('set_file_owner_and_permissions.html', return_dict, context_instance=django.template.context.RequestContext(request))
  
    else:
  
      # Shd be an save request
      form = common_forms.SetFileOwnerAndPermissionsForm(request.POST, user_list = users, group_list = groups)
      return_dict["form"] = form
      if form.is_valid():
        cd = form.cleaned_data
        ret, err = file_processing.set_dir_ownership_and_permissions(cd)
        if not ret:
          if err:
            raise Exception(err)
          else:
            raise Exception("Error setting directory ownership/permissions.")
  
        audit_str = "Modified directory ownsership/permissions for %s"%cd["path"]
        audit.audit("modify_dir_owner_permissions", audit_str, request.META["REMOTE_ADDR"])
  
        return django.http.HttpResponseRedirect('/view_zfs_pools?ack=set_permissions')
  
      else:
        #Invalid form
        return django.shortcuts.render_to_response('set_file_owner_and_permissions.html', return_dict, context_instance=django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Modify ownership/permissions on a directory'
    return_dict['tab'] = 'dir_permissions_tab'
    return_dict["error"] = 'Error modifying directory ownership/permissions'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def _owner_readable(st):
  return bool(st.st_mode & stat.S_IRUSR)
def _owner_writeable(st):
  return bool(st.st_mode & stat.S_IWUSR)
def _owner_executeable(st):
  return bool(st.st_mode & stat.S_IXUSR)

def _group_readable(st):
  return bool(st.st_mode & stat.S_IRGRP)
def _group_writeable(st):
  return bool(st.st_mode & stat.S_IWGRP)
def _group_executeable(st):
  return bool(st.st_mode & stat.S_IXGRP)

def _other_readable(st):
  return bool(st.st_mode & stat.S_IROTH)
def _other_writeable(st):
  return bool(st.st_mode & stat.S_IWOTH)
def _other_executeable(st):
  return bool(st.st_mode & stat.S_IXOTH)

'''
