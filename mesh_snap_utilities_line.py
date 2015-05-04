﻿### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

# Contact for more information about the Addon:
# Email:    germano.costa@ig.com.br
# Twitter:  wii_mano @mano_wii

bl_info = {
    "name": "Snap_Utilities_Line",
    "author": "Germano Cavalcante",
    "version": (4, 0),
    "blender": (2, 74, 0),
    "location": "View3D > TOOLS > Snap Utilities > snap utilities",
    "description": "Extends Blender Snap controls",
    "wiki_url" : "http://blenderartists.org/forum/showthread.php?363859-Addon-CAD-Snap-Utilities",
    "category": "Mesh"}
    
import bpy, bgl, bmesh, mathutils, math
#from space_view3d_panel_measure import getUnitsInfo, convertDistance
from mathutils import Vector, Matrix
from bpy_extras import view3d_utils

PRECISION = 5

def getUnitsInfo():
        scale = bpy.context.scene.unit_settings.scale_length
        unit_system = bpy.context.scene.unit_settings.system
        separate_units = bpy.context.scene.unit_settings.use_separate
        if unit_system == 'METRIC':
                scale_steps = ((1000, 'km'), (1, 'm'), (1 / 100, 'cm'),
                    (1 / 1000, 'mm'), (1 / 1000000, '\u00b5m'))
        elif unit_system == 'IMPERIAL':
                scale_steps = ((5280, 'mi'), (1, '\''),
                    (1 / 12, '"'), (1 / 12000, 'thou'))
                scale /= 0.3048  # BU to feet
        else:
                scale_steps = ((1, ' BU'),)
                separate_units = False

        return (scale, scale_steps, separate_units)
    
def convertDistance(val, units_info):
        scale, scale_steps, separate_units = units_info
        sval = val * scale
        idx = 0
        while idx < len(scale_steps) - 1:
                if sval >= scale_steps[idx][0]:
                        break
                idx += 1
        factor, suffix = scale_steps[idx]
        sval /= factor
        if not separate_units or idx == len(scale_steps) - 1:
                dval = str(round(sval, PRECISION)) + suffix
        else:
                ival = int(sval)
                dval = str(round(ival, PRECISION)) + suffix
                fval = sval - ival
                idx += 1
                while idx < len(scale_steps):
                        fval *= scale_steps[idx - 1][0] / scale_steps[idx][0]
                        if fval >= 1:
                                dval += ' ' \
                                    + ("%.1f" % fval) \
                                    + scale_steps[idx][1]
                                break
                        idx += 1
        return dval

def navigation(self, context, event):
    rv3d = context.region_data
    if not hasattr(self, 'navigation_cache'): # or self.navigation_cache == False:
        self.navigation_cache = True
        self.keys_rotate = []
        self.keys_move = []
        self.keys_zoom = []
        for key in context.window_manager.keyconfigs.user.keymaps['3D View'].keymap_items:
            if key.idname == 'view3d.rotate':
                #self.keys_rotate[key.id]={'Alt': key.alt, 'Ctrl': key.ctrl, 'Shift':key.shift, 'Type':key.type, 'Value':key.value}
                self.keys_rotate.append((key.alt, key.ctrl, key.shift, key.type, key.value))
            if key.idname == 'view3d.move':
                self.keys_move.append((key.alt, key.ctrl, key.shift, key.type, key.value))
            if key.idname == 'view3d.zoom':
                self.keys_zoom.append((key.alt, key.ctrl, key.shift, key.type, key.value, key.properties.delta))
                if key.type == 'WHEELINMOUSE':
                    self.keys_zoom.append((key.alt, key.ctrl, key.shift, 'WHEELDOWNMOUSE', key.value, key.properties.delta))
                if key.type == 'WHEELOUTMOUSE':
                    self.keys_zoom.append((key.alt, key.ctrl, key.shift, 'WHEELUPMOUSE', key.value, key.properties.delta))

    evkey = (event.alt, event.ctrl, event.shift, event.type, event.value)
    for key in self.keys_rotate:
        if evkey == key:
            bpy.ops.view3d.rotate('INVOKE_DEFAULT')
            break
    for key in self.keys_move:
        if evkey == key:
            if event.shift:
                if self.bool_constrain and (1 not in self.vector_constrain):
                    self.bool_constrain = False
            bpy.ops.view3d.move('INVOKE_DEFAULT')
            break
    for key in self.keys_zoom:
        if evkey == key[0:5]:
            delta = key[5]
            if delta == 0:
                bpy.ops.view3d.zoom('INVOKE_DEFAULT')
                break
            else:
                rv3d.view_distance += delta*rv3d.view_distance/6
                rv3d.view_location -= delta*(self.location - rv3d.view_location)/6
                break

def location_3d_to_region_2d(region, rv3d, coord):
    prj = rv3d.perspective_matrix * Vector((coord[0], coord[1], coord[2], 1.0))
    width_half = region.width / 2.0
    height_half = region.height / 2.0
    return Vector((width_half + width_half * (prj.x / prj.w),
                   height_half + height_half * (prj.y / prj.w),
                   ))

def out_Location(rv3d, region, orig, vector):
    view_matrix = rv3d.view_matrix
    v1 = Vector((int(view_matrix[0][0]*1.5),int(view_matrix[0][1]*1.5),int(view_matrix[0][2]*1.5)))
    v2 = Vector((int(view_matrix[1][0]*1.5),int(view_matrix[1][1]*1.5),int(view_matrix[1][2]*1.5)))

    hit = mathutils.geometry.intersect_ray_tri(Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,0)), (vector), (orig), False)
    if hit == None:
        hit = mathutils.geometry.intersect_ray_tri(v1, v2, Vector((0,0,0)), (vector), (orig), False)        
    if hit == None:
        hit = mathutils.geometry.intersect_ray_tri(v1, v2, Vector((0,0,0)), (-vector), (orig), False)
    if hit == None:
        hit = Vector((0,0,0))
    return hit

def SnapUtilities(self, context, obj_matrix_world, bm_geom, bool_update, vert_perp, mcursor, bool_constrain, vector_constrain, outer_verts):
    rv3d = context.region_data
    region = context.region
    if not hasattr(self, 'const'):
        self.const = None

    if bool_constrain == False and self.const != None:
        self.const = None

    if isinstance(bm_geom, bmesh.types.BMVert):
        if not hasattr(self, 'bvert') or self.bvert != bm_geom or bool_update == True:
            self.bvert = bm_geom
            self.vert = obj_matrix_world * self.bvert.co
            self.Pvert = location_3d_to_region_2d(region, rv3d, self.vert)

        if bool_constrain == True:
            if self.const == None:
                self.const = self.vert
            #point = Vector([(self.vert[index] if vector_constrain==1 else self.const[index]) for index, vector_constrain in enumerate(vector_constrain)])
            point = mathutils.geometry.intersect_point_line(self.vert, self.const, (self.const+vector_constrain))[0]
            #point = vector_constrain.project(self.vert)
            return point, 'VERT' #or 'FACE' or 'OUT' or 'EDGE'
        #else:
        return self.vert, 'VERT'
                
    if isinstance(bm_geom, bmesh.types.BMEdge):
        if not hasattr(self, 'bedge') or self.bedge != bm_geom or bool_update == True:
            self.bedge = bm_geom
            self.vert0 = obj_matrix_world*self.bedge.verts[0].co
            self.vert1 = obj_matrix_world*self.bedge.verts[1].co
            self.po_cent = (self.vert0+self.vert1)/2
            self.Pcent = location_3d_to_region_2d(region, rv3d, self.po_cent)
            self.Pvert0 = location_3d_to_region_2d(region, rv3d, self.vert0)
            self.Pvert1 = location_3d_to_region_2d(region, rv3d, self.vert1)
                
            if vert_perp != None and vert_perp not in [v.co for v in self.bedge.verts]:
                point_perpendicular = mathutils.geometry.intersect_point_line(vert_perp, self.vert0, self.vert1)
                self.po_perp = point_perpendicular[0]
                self.Pperp = location_3d_to_region_2d(region, rv3d, self.po_perp)

        if bool_constrain == True:
            if self.const == None:
                if vert_perp != None:
                    self.const = vert_perp
                else:
                    self.const = self.po_cent

            point = mathutils.geometry.intersect_line_line(self.const, (self.const+vector_constrain), self.vert0, self.vert1)
            if point == None:
                orig = view3d_utils.region_2d_to_origin_3d(region, rv3d, mcursor)
                view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mcursor)
                end = orig + view_vector
                point = mathutils.geometry.intersect_line_line(self.const, (self.const+vector_constrain), orig, end)
            return point[0], 'EDGE'

        else:
            if hasattr(self, 'Pperp') and abs(self.Pperp[0]-mcursor[0]) < 10 and abs(self.Pperp[1]-mcursor[1]) < 10:
                return self.po_perp, 'PERPENDICULAR'

            elif abs(self.Pcent[0]-mcursor[0]) < 10 and abs(self.Pcent[1]-mcursor[1]) < 10:
                return self.po_cent, 'CENTER'
            
            else:
                orig = view3d_utils.region_2d_to_origin_3d(region, rv3d, mcursor)
                view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mcursor)
                end = orig + view_vector
                point = mathutils.geometry.intersect_line_line(self.vert0, self.vert1, orig, end)
                return point[0], 'EDGE'

    if isinstance(bm_geom, bmesh.types.BMFace):
        if not hasattr(self, 'bface') or self.bface != bm_geom or bool_update == True:
            self.bface = bm_geom
            self.face_center = obj_matrix_world*bm_geom.calc_center_median()
            self.face_normal = bm_geom.normal*obj_matrix_world.inverted()
            
        orig = view3d_utils.region_2d_to_origin_3d(region, rv3d, mcursor)
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mcursor)
        end = orig + view_vector
        if bool_constrain == True:
            if self.const == None:
                if vert_perp != None:
                    self.const = vert_perp
                else:
                    self.const = mathutils.geometry.intersect_line_plane(orig, end, self.face_center, self.face_normal, False)
            point = mathutils.geometry.intersect_line_line(self.const, (self.const+vector_constrain), orig, end)
            return point[0], 'FACE'
        #else:
        point = mathutils.geometry.intersect_line_plane(orig, end, self.face_center, self.face_normal, False)
        return point, 'FACE'
    
    else:
        orig = view3d_utils.region_2d_to_origin_3d(region, rv3d, mcursor)
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mcursor)
        end = orig + view_vector * 1000
        scene = bpy.context.scene
        result, object, matrix, location, normal = scene.ray_cast(orig, end)
        if result:
            type = 'FACE'
            if outer_verts:
                try:
                    # get the ray relative to the object
                    matrix_inv = matrix.inverted()
                    ray_origin_obj = matrix_inv * orig
                    ray_target_obj = matrix_inv * end
                    location, normal, face_index = object.ray_cast(ray_origin_obj, ray_target_obj)
                    location = matrix*location
                    verts = object.data.polygons[face_index].vertices
                    v_dist = 10

                    for i in verts:
                        v_co = matrix*object.data.vertices[i].co
                        v_2d = location_3d_to_region_2d(region, rv3d, v_co)
                        dist = (Vector(mcursor)-v_2d).length
                        if dist < v_dist:
                            v_dist = dist
                            location = v_co
                            type = 'VERT'
                except:
                    print("fail")
        else:
            location = out_Location(rv3d, region, orig, view_vector)
            type = 'OUT'

        if bool_constrain == True:
            if self.const == None:
                if vert_perp != None:
                    self.const = vert_perp
                else:
                    self.const = location
            if type == 'VERT':
                self.vert = location
                point = mathutils.geometry.intersect_point_line(location, self.const, (self.const+vector_constrain))
            else:
                point = mathutils.geometry.intersect_line_line(self.const, (self.const+vector_constrain), orig, end)
            location = point[0]
        return location, type

def get_isolated_edges(bmvert):
    linked = [c for c in bmvert.link_edges[:] if c.link_faces[:] == []]
    for a in linked:
        edges = [b for c in a.verts[:] if c.link_faces[:] == [] for b in c.link_edges[:] if b not in linked]
        for e in edges:
            linked.append(e)
    return linked

def draw_line(self, obj, Bmesh, bm_geom, location):
    if not hasattr(self, 'list_vertices'):
        self.list_vertices = []

    if not hasattr(self, 'list_edges'):
        self.list_edges = []

    if not hasattr(self, 'list_faces'):
        self.list_faces = []

    if bm_geom == None:
        vertices = (bmesh.ops.create_vert(Bmesh, co=(location)))
        self.list_vertices.append(vertices['vert'][0])

    elif isinstance(bm_geom, bmesh.types.BMVert):
        if (bm_geom.co - location).length < .01:
            if self.list_vertices == [] or self.list_vertices[-1] != bm_geom:
                self.list_vertices.append(bm_geom)
        else:
            vertices = bmesh.ops.create_vert(Bmesh, co=(location))
            self.list_vertices.append(vertices['vert'][0])
        
    elif isinstance(bm_geom, bmesh.types.BMEdge):
        self.list_edges.append(bm_geom)
        vector_p0_l = (bm_geom.verts[0].co-location)
        vector_p1_l = (bm_geom.verts[1].co-location)
        wedge = vector_p0_l.y*vector_p1_l.x - vector_p0_l.x*vector_p1_l.y

        if round(wedge, 4) == 0: # or round(vector_p0_l.angle(vector_p1_l), 2) == 3.14:
            factor = vector_p0_l.length/bm_geom.calc_length()
            vertex0 = bmesh.utils.edge_split(bm_geom, bm_geom.verts[0], factor)
            self.list_vertices.append(vertex0[1])
            #self.list_edges.append(vertex0[0])

        else: # constrain point is near
            vertices = bmesh.ops.create_vert(Bmesh, co=(location))
            self.list_vertices.append(vertices['vert'][0])

    elif isinstance(bm_geom, bmesh.types.BMFace):
        self.list_faces.append(bm_geom)
        vertices = (bmesh.ops.create_vert(Bmesh, co=(location)))
        self.list_vertices.append(vertices['vert'][0])
    
    # draw, split and create face
    if len(self.list_vertices) >= 2:
        V1 = self.list_vertices[-2]
        V2 = self.list_vertices[-1]
        #V2_link_verts = [x for y in [a.verts for a in V2.link_edges] for x in y if x != V2]
        for edge in V2.link_edges:
            if V1 in edge.verts:
                self.list_edges.append(edge)
                break
        else: #if V1 not in V2_link_verts:
            if V2.link_edges[:] == []:
                edge = Bmesh.edges.new([V1, V2])
                self.list_edges.append(edge)
            else:
                face = [x for x in V2.link_faces[:] if x in V1.link_faces[:]]
                if face != []:# and self.list_faces == []:
                    self.list_faces = face
                    
                elif V1.link_faces[:] == [] or V2.link_faces[:] == []:
                    if self.list_faces == []:
                        if V1.link_faces[:] != []:
                            Vfaces = V1.link_faces
                            Vtest = V2.co
                        elif V2.link_faces[:] != []:
                            Vfaces = V2.link_faces
                            Vtest = V1.co
                        else:
                            Vfaces = []
                        for face in Vfaces:
                            testface = bmesh.geometry.intersect_face_point(face, Vtest)
                            if testface:
                                self.list_faces.append(face)

                if self.list_faces != []:
                    edge = Bmesh.edges.new([V1, V2])
                    self.list_edges.append(edge)
                    ed_list = get_isolated_edges(V2)
                    for face in list(set(self.list_faces)):
                        facesp = bmesh.utils.face_split_edgenet(face, list(set(ed_list)))
                        self.list_faces = []
                else:
                    if self.intersect:
                        facesp = bmesh.ops.connect_vert_pair(Bmesh, verts = [V1, V2])
                    if not self.intersect or facesp['edges'] == []:
                        edge = Bmesh.edges.new([V1, V2])
                        self.list_edges.append(edge)
                    else:   
                        for edge in facesp['edges']:
                            self.list_edges.append(edge)
                bmesh.update_edit_mesh(obj.data, tessface=True, destructive=True)

        # create face
        if self.create_face:
            ed_list = self.list_edges.copy()
            for edge in V2.link_edges:
                for vert in edge.verts:
                    if vert in self.list_vertices:
                        ed_list.append(edge)
                        for edge in get_isolated_edges(V2):
                            if edge not in ed_list:
                                ed_list.append(edge)
                        bmesh.ops.edgenet_fill(Bmesh, edges = list(set(ed_list)))
                        bmesh.update_edit_mesh(obj.data, tessface=True, destructive=True)
                        break
            #print('face created')

    return [obj.matrix_world*a.co for a in self.list_vertices]

def draw_callback_px(self, context):
    # draw 3d point OpenGL in the 3D View
    bgl.glEnable(bgl.GL_BLEND)

    if self.bool_constrain:
        if hasattr(self, 'vert') and self.type == 'VERT':
            bgl.glColor4f(1.0,1.0,1.0,0.5)
            bgl.glDepthRange(0,0)
            bgl.glPointSize(5)
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glVertex3f(*self.vert)
            bgl.glEnd()
        if self.vector_constrain == Vector((1,0,0)):
            Color4f = (self.axis_x_color + (1.0,))
        elif self.vector_constrain == Vector((0,1,0)):
            Color4f = (self.axis_y_color + (1.0,))
        elif self.vector_constrain == Vector((0,0,1)):
            Color4f = (self.axis_z_color + (1.0,))
        else:
            Color4f = self.constrain_shift_color
    else:
        if self.type == 'OUT':
            Color4f = self.out_color 
        elif self.type == 'FACE':
            Color4f = self.face_color
        elif self.type == 'EDGE':
            Color4f = self.edge_color
        elif self.type == 'VERT':
            Color4f = self.vert_color
        elif self.type == 'CENTER':
            Color4f = self.center_color
        elif self.type == 'PERPENDICULAR':
            Color4f = self.perpendicular_color

    bgl.glColor4f(*Color4f)
    bgl.glDepthRange(0,0)    
    bgl.glPointSize(10)    
    bgl.glBegin(bgl.GL_POINTS)
    bgl.glVertex3f(*self.location)
    bgl.glEnd()

    # draw 3d line OpenGL in the 3D View
    bgl.glDepthRange(0,0.9999)
    bgl.glColor4f(1.0, 0.8, 0.0, 1.0)    
    bgl.glLineWidth(2)    
    bgl.glEnable(bgl.GL_LINE_STIPPLE)
    bgl.glBegin(bgl.GL_LINE_STRIP)
    for vert_co in self.list_vertices_co:
        bgl.glVertex3f(*vert_co)        
    bgl.glVertex3f(*self.location)        
    bgl.glEnd()

    # restore opengl defaults
    bgl.glDepthRange(0,1)
    bgl.glPointSize(1)
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glDisable(bgl.GL_LINE_STIPPLE)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)

    a = ""
    if self.list_vertices_co != [] and self.length_entered == "":
        length = (self.list_vertices_co[-1]-self.location).length
        length = convertDistance(length, self.uinfo)
        a = 'length: '+ length
    elif self.list_vertices_co != [] and self.length_entered != "":
        a = 'length: '+ self.length_entered

    context.area.header_text_set("hit: %.3f %.3f %.3f %s" % (self.location[0], self.location[1], self.location[2], a))

class Constrain:
    keys = {
        'X': Vector((1,0,0)),
        'Y': Vector((0,1,0)),
        'Z': Vector((0,0,1)),
        'RIGHT_SHIFT': 'shift',
        'LEFT_SHIFT': 'shift',
        }

    def __init__(self, bool_constrain = False, vector_constrain = None):
        self.bool_constrain = bool_constrain
        self.vector_constrain = vector_constrain

    def modal(self, context, event):
        if event.value == 'PRESS':
            if self.vector_constrain == self.keys[event.type] or self.bool_constrain == False:
                self.bool_constrain = self.bool_constrain == False
                self.vector_constrain = self.keys[event.type]
                
            elif event.shift:
                if self.vector_constrain not in self.keys.values():
                    self.bool_constrain = self.bool_constrain == False
                    self.vector_constrain = self.keys[event.type]
                    
            else:
                self.vector_constrain = self.keys[event.type]
                    
        return self.bool_constrain, self.vector_constrain
    
class CharMap:
    ascii = {
        ".", "-", "+", "1", "2", "3",
        "4", "5", "6", "7", "8", "9", "0",
        " ", "/", "*", "'", "\""
        #"="
        }
    type = {
        'BACK_SPACE', 'DEL'
        }

    def __init__(self, length_entered = ""):
        self.length_entered = length_entered

    def modal(self, context, event):
        c = event.ascii
        self.length_entered += c
        if event.type in self.type and len(self.length_entered) >= 1:
            self.length_entered = self.length_entered[:-1]

        return self.length_entered

class MESH_OT_snap_utilities_line(bpy.types.Operator):
    """ Draw edges. Connect them to split faces."""
    bl_idname = "mesh.snap_utilities_line"
    bl_label = "Line Tool"
    bl_options = {'REGISTER', 'UNDO'}
    
    def modal(self, context, event):
        navigation(self, context, event)

        if context.area:
            context.area.tag_redraw()

        if event.ctrl:
            if event.type == 'Z' and event.value == 'PRESS':
                bpy.ops.ed.undo()
                self.bool_constrain = False
                self.list_vertices_co = []
                self.list_vertices = []
                self.list_edges = []
                self.list_faces = []
                self.obj = bpy.context.active_object
                self.obj_matrix = self.obj.matrix_world.copy()
                self.bm = bmesh.from_edit_mesh(self.obj.data)
                return {'RUNNING_MODAL'}

        elif event.type in Constrain.keys:
            Constrain2 = Constrain(self.bool_constrain, self.vector_constrain)
            self.bool_constrain, self.vector_constrain = Constrain2.modal(context, event)
            if self.vector_constrain == 'shift':
                if isinstance(self.geom, bmesh.types.BMEdge):
                    #self.vector_constrain = self.obj_matrix*self.geom.verts[1].co-self.obj_matrix*self.geom.verts[0].co
                    self.vector_constrain = (self.geom.verts[1].co-self.geom.verts[0].co)*self.obj_matrix.inverted()
                else:
                    self.bool_constrain = False
            self.bool_update = True

        if event.type == 'MOUSEMOVE' or self.bool_update:
            if self.rv3d.view_matrix != self.rotMat:
                self.rotMat = self.rv3d.view_matrix
                self.bool_update = True
            else:
                self.bool_update = False

            try:
                self.geom = self.bm.select_history[0]
            except: # IndexError or AttributeError:
                self.geom = None

            x, y = (event.mouse_region_x, event.mouse_region_y)
            if self.geom != None:
                self.lastgeom = self.geom
                bpy.ops.mesh.select_all(action='DESELECT')

            bpy.ops.view3d.select(location=(x, y))

            if self.list_vertices_co != []:
                bm_vert_to_perpendicular = self.list_vertices_co[-1]
            else:
                bm_vert_to_perpendicular = None
            
            
            outer_verts = self.outer_verts and not self.keytab

            self.location, self.type = SnapUtilities(self, context, self.obj_matrix,
                    self.geom, self.bool_update, bm_vert_to_perpendicular, (x, y), 
                    self.bool_constrain, self.vector_constrain, outer_verts)

        elif event.value == 'PRESS':
            if event.ascii in CharMap.ascii or event.type in CharMap.type:
                CharMap2 = CharMap(self.length_entered)
                self.length_entered = CharMap2.modal(context, event)
                #print(self.length_entered)
                
            elif event.type == 'LEFTMOUSE':
                # SNAP 2D
                snap_3d = self.location
                Lsnap_3d = self.obj_matrix.inverted()*snap_3d
                Snap_2d = location_3d_to_region_2d(self.region, self.rv3d, snap_3d)
                if self.bool_constrain and isinstance(self.geom, bmesh.types.BMVert): # SELECT FIRST
                    bpy.ops.view3d.select(location=(int(Snap_2d[0]), int(Snap_2d[1])))
                    try:
                        geom2 = self.bm.select_history[0]
                    except: # IndexError or AttributeError:
                        geom2 = None
                else:
                    geom2 = self.geom
                self.bool_constrain = False
                self.list_vertices_co = draw_line(self, self.obj, self.bm, geom2, Lsnap_3d)
                bpy.ops.ed.undo_push(message="Add an undo step *function may be moved*")

            elif event.type == 'TAB':
                self.keytab = self.keytab == False
                if self.keytab:            
                    context.tool_settings.mesh_select_mode = (False, False, True)
                else:
                    context.tool_settings.mesh_select_mode = (True, True, True)

        elif event.value == 'RELEASE':
            if event.type in {'RET', 'NUMPAD_ENTER'}:
                if self.length_entered != "" and self.list_vertices_co != []:
                    try:
                        unit_system = context.scene.unit_settings.system
                        text_value = bpy.utils.units.to_value(unit_system, 'LENGTH', self.length_entered)
                        vector = (self.location-self.list_vertices_co[-1]).normalized()
                        location = (self.list_vertices_co[-1]+(vector*text_value))
                        G_location = self.obj_matrix.inverted()*location
                        self.list_vertices_co = draw_line(self, self.obj, self.bm, self.geom, G_location)
                        self.length_entered = ""
                        self.bool_constrain = False

                    except:# ValueError:
                        self.report({'INFO'}, "Operation not supported yet")

            elif event.type in {'RIGHTMOUSE', 'ESC'}:
                if self.list_vertices_co == [] or event.type == 'ESC':                
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                    context.tool_settings.mesh_select_mode = self.select_mode
                    context.area.header_text_set()
                    context.user_preferences.view.use_rotate_around_active = self.use_rotate_around_active
                    if not self.is_editmode:
                        bpy.ops.object.editmode_toggle()
                    return {'FINISHED'}
                else:
                    self.bool_constrain = False
                    self.list_vertices = []
                    self.list_vertices_co = []
                    self.list_faces = []
                
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):        
        if context.space_data.type == 'VIEW_3D':
            self.region = context.region
            self.rv3d = context.region_data

            create_new_obj = context.user_preferences.addons[__name__].preferences.create_new_obj
            if context.mode == 'OBJECT' and create_new_obj:

                mesh = bpy.data.meshes.new("")
                mesh.from_pydata([context.scene.cursor_location], [], [])
                mesh.update()
                obj = bpy.data.objects.new("", mesh)
                context.scene.objects.link(obj)
                bpy.ops.object.select_all(action = "DESELECT")
                obj.select = True
                context.scene.objects.active = obj

            bgl.glEnable(bgl.GL_POINT_SMOOTH)
            self.is_editmode = context.object.data.is_editmode
            bpy.ops.object.mode_set(mode='EDIT')
            context.space_data.use_occlude_geometry = True
            self.uinfo = getUnitsInfo()

            self.use_rotate_around_active = context.user_preferences.view.use_rotate_around_active
            context.user_preferences.view.use_rotate_around_active = True
            
            self.select_mode = context.tool_settings.mesh_select_mode[:]
            context.tool_settings.mesh_select_mode = (True, True, True)
            
            self.rotMat = self.rv3d.view_matrix
            self.obj = bpy.context.active_object
            self.obj_matrix = self.obj.matrix_world.copy()
            self.bm = bmesh.from_edit_mesh(self.obj.data)
            
            self.list_vertices_co = []
            self.bool_constrain = False
            self.bool_update = False
            self.vector_constrain = None
            self.keytab = False
            self.length_entered = ""
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (self, context), 'WINDOW', 'POST_VIEW')
            context.window_manager.modal_handler_add(self)
            
            self.out_color = context.user_preferences.addons[__name__].preferences.out_color
            self.face_color = context.user_preferences.addons[__name__].preferences.face_color
            self.edge_color = context.user_preferences.addons[__name__].preferences.edge_color
            self.vert_color = context.user_preferences.addons[__name__].preferences.vert_color
            self.center_color = context.user_preferences.addons[__name__].preferences.center_color
            self.perpendicular_color = context.user_preferences.addons[__name__].preferences.perpendicular_color
            self.constrain_shift_color = context.user_preferences.addons[__name__].preferences.constrain_shift_color

            self.axis_x_color = tuple(context.user_preferences.themes[0].user_interface.axis_x)
            self.axis_y_color = tuple(context.user_preferences.themes[0].user_interface.axis_y)
            self.axis_z_color = tuple(context.user_preferences.themes[0].user_interface.axis_z)

            self.create_face = context.user_preferences.addons[__name__].preferences.create_face
            self.intersect = context.user_preferences.addons[__name__].preferences.intersect
            self.outer_verts = context.user_preferences.addons[__name__].preferences.outer_verts

            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}

def update_panel(self, context):
    try:
        bpy.utils.unregister_class(PanelSnapUtilities)
    except:
        print(PanelSnapUtilities.bl_category, context.user_preferences.addons[__name__].preferences.category)
        pass
    PanelSnapUtilities.bl_category = context.user_preferences.addons[__name__].preferences.category
    bpy.utils.register_class(PanelSnapUtilities)

class PanelSnapUtilities(bpy.types.Panel) :
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    #bl_context = "mesh_edit"
    #bl_category = addon_prefs.category #"Snap Utilities"
    bl_category = "Snap Utilities"
    bl_label = "snap utilities"
    '''
    @classmethod
    def poll(cls, context):
        return (context.object is not None and
                context.object.type == 'MESH')
    '''
    def draw(self, context):
        layout = self.layout
        TheCol = layout.column(align = True)
        TheCol.operator("mesh.snap_utilities_line", text = "Line", icon="GREASEPENCIL")
        
        self.addon_prefs = context.user_preferences.addons[__name__].preferences
        
        box = layout.box()
        if not self.addon_prefs.expand_snap_settings:
            # expand button
            box.prop(self.addon_prefs, "expand_snap_settings", icon="TRIA_RIGHT", icon_only=True,
                text="Settings:", emboss=False)
        else:
            # expand button
            box.prop(self.addon_prefs, "expand_snap_settings", icon="TRIA_DOWN", icon_only=True,
                text="Settings:", emboss=False) # icon_only broken?
            box.label(text="Snap Items:")
            box.prop(self.addon_prefs, "outer_verts")
            box.label(text="Line Tool:")
            box.prop(self.addon_prefs, "intersect")
            box.prop(self.addon_prefs, "create_face")
            box.prop(self.addon_prefs, "create_new_obj")

class SnapAddonPreferences(bpy.types.AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__
    
    intersect = bpy.props.BoolProperty(
            name="Intersect",
            description="intersects created line with the existing edges, even if the lines do not intersect.",
            default=True)

    create_new_obj = bpy.props.BoolProperty(
            name="Create a new object",
            description="If have not a active object, or the active object is not in edit mode, it creates a new object.",
            default=False)

    create_face = bpy.props.BoolProperty(
            name="Create faces",
            description="Create faces defined by enclosed edges.",
            default=False)
            
    outer_verts = bpy.props.BoolProperty(
            name="Snap to outer vertices",
            description="The vertices of the objects are not activated also snapped.",
            default=True)
            
    expand_snap_settings = bpy.props.BoolProperty(
            name="Expand",
            description="Expand, to display the settings",
            default=False)
            
    category = bpy.props.StringProperty(
            name="Category",
            description="Choose a name for the category of the panel",
            default="Snap Utilities",
            update=update_panel)

    out_color = bpy.props.FloatVectorProperty(name="OUT", default=(0.0, 0.0, 0.0, 0.5), size=4, subtype="COLOR", min=0, max=1)
    face_color = bpy.props.FloatVectorProperty(name="FACE", default=(1.0, 0.8, 0.0, 1.0), size=4, subtype="COLOR", min=0, max=1)
    edge_color = bpy.props.FloatVectorProperty(name="EDGE", default=(0.0, 0.8, 1.0, 1.0), size=4, subtype="COLOR", min=0, max=1)
    vert_color = bpy.props.FloatVectorProperty(name="VERT", default=(1.0, 0.5, 0.0, 1.0), size=4, subtype="COLOR", min=0, max=1)
    center_color = bpy.props.FloatVectorProperty(name="CENTER", default=(1.0, 0.0, 1.0, 1.0), size=4, subtype="COLOR", min=0, max=1)
    perpendicular_color = bpy.props.FloatVectorProperty(name="PERPENDICULAR", default=(0.1, 0.5, 0.5, 1.0), size=4, subtype="COLOR", min=0, max=1)
    constrain_shift_color = bpy.props.FloatVectorProperty(name="SHIFT CONSTRAIN", default=(0.8, 0.5, 0.4, 1.0), size=4, subtype="COLOR", min=0, max=1)

    def draw(self, context):
        layout = self.layout

        layout.label(text="Snap Colors:")
        split = layout.split()

        col = split.column()
        col.prop(self, "out_color")
        col.prop(self, "constrain_shift_color")
        col = split.column()
        col.prop(self, "face_color")
        col = split.column()
        col.prop(self, "edge_color")        
        col = split.column()
        col.prop(self, "vert_color")
        col = split.column()
        col.prop(self, "center_color")
        col = split.column()
        col.prop(self, "perpendicular_color")

        row = layout.row()

        col = row.column()
        col.label(text="Category:")
        col.prop(self, "category", text="")
        col.label(text="Snap Items:")
        col.prop(self, "outer_verts")

        row.separator()

        col = row.column()
        col.label(text="Line Tool:")
        col.prop(self, "intersect")
        col.prop(self, "create_face")
        col.prop(self, "create_new_obj")

def register():
    print('Addon', __name__, 'registered')
    bpy.utils.register_class(SnapAddonPreferences)
    bpy.utils.register_class(MESH_OT_snap_utilities_line)
    update_panel(None, bpy.context)
    #bpy.utils.register_class(PanelSnapUtilities)

def unregister():
    bpy.utils.unregister_class(PanelSnapUtilities)
    bpy.utils.unregister_class(MESH_OT_snap_utilities_line)
    bpy.utils.unregister_class(SnapAddonPreferences)

if __name__ == "__main__":
    __name__ = "mesh_snap_utilities_line"
    register()
